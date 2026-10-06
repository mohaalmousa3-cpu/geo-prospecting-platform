"""Storage abstraction. V1 has one implementation: local filesystem (ADR-0006).

Keys are logical (`aoi/<id>/file.tif`); user-supplied paths are never used directly.
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

STAGING_DIR = ".staging"  # reserved: never a valid first key segment


class StorageKeyError(ValueError):
    """The key is unsafe or malformed."""


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def open_path(self, key: str) -> Path:
        """Return a local filesystem path for the key (for tools needing a real file)."""

    @abstractmethod
    def delete_staging(self, key: str) -> None:
        """Remove the staging file that `put(key, …)` uses (idempotent). Touches only that one
        derived name."""

    @abstractmethod
    def iter_keys(self) -> Iterator[str]:
        """Every stored key (staging files excluded). For report-only reconciliation."""

    @abstractmethod
    def iter_staging(self) -> Iterator[tuple[str, float, int]]:
        """(name, mtime, size) of every staging file. For report-only reconciliation."""


class LocalStorage(StorageBackend):
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or "\x00" in key or "\\" in key:
            raise StorageKeyError("empty key or illegal character")
        posix = PurePosixPath(key)
        parts = key.split("/")
        if posix.is_absolute() or any(p in ("..", ".", "") for p in parts):
            raise StorageKeyError("key must be a relative path without '.', '..' or empty parts")
        if parts[0] == STAGING_DIR:
            raise StorageKeyError(f"'{STAGING_DIR}' is reserved")
        target = (self._root / posix).resolve()
        if target == self._root or not target.is_relative_to(self._root):
            raise StorageKeyError("key escapes the storage root")
        return target

    def _staging_path(self, key: str) -> Path:
        """Deterministic staging name derived from the (never reused) key, so only its owner can
        find it."""
        self._resolve(key)  # validates the key
        return self._root / STAGING_DIR / f"{hashlib.sha256(key.encode()).hexdigest()}.part"

    def put(self, key: str, data: bytes) -> None:
        """Write `data` to a staging file, flush it, rename atomically to `key`, flush the directory
        entry."""
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        # re-check after mkdir: a symlinked parent could point outside the root
        if not target.parent.resolve().is_relative_to(self._root):
            raise StorageKeyError("key escapes the storage root")
        staging = self._staging_path(key)
        staging.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(staging, "wb") as fh:  # noqa: PTH123
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(staging, target)
            self._fsync_dir(target.parent)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def delete_staging(self, key: str) -> None:
        self._staging_path(key).unlink(missing_ok=True)

    def iter_keys(self) -> Iterator[str]:
        for f in sorted(self._root.rglob("*")):
            rel = f.relative_to(self._root)
            if f.is_file() and rel.parts[0] != STAGING_DIR:
                yield rel.as_posix()

    def iter_staging(self) -> Iterator[tuple[str, float, int]]:
        d = self._root / STAGING_DIR
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file():
                    st = f.stat()
                    yield f.name, st.st_mtime, st.st_size

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def open_path(self, key: str) -> Path:
        return self._resolve(key)
