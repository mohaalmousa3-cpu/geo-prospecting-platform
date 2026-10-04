"""Storage abstraction. V1 has one implementation: local filesystem (ADR-0006).

Keys are logical (`aoi/<id>/file.tif`); user-supplied paths are never used directly.
"""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath


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


class LocalStorage(StorageBackend):
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or "\x00" in key or "\\" in key:
            raise StorageKeyError("empty key or illegal character")
        posix = PurePosixPath(key)
        if posix.is_absolute() or any(p in ("..", ".", "") for p in key.split("/")):
            raise StorageKeyError("key must be a relative path without '.', '..' or empty parts")
        target = (self._root / posix).resolve()
        if target == self._root or not target.is_relative_to(self._root):
            raise StorageKeyError("key escapes the storage root")
        return target

    def put(self, key: str, data: bytes) -> None:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        # re-check after mkdir: a symlinked parent could point outside the root
        if not target.parent.resolve().is_relative_to(self._root):
            raise StorageKeyError("key escapes the storage root")
        fd, tmp = tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def open_path(self, key: str) -> Path:
        return self._resolve(key)
