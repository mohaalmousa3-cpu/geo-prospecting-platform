"""Hardened in-memory ZIP reading for KMZ / zipped Shapefile uploads (ADR-0012 §8).

Nothing is extracted to disk. Declared sizes are never trusted: bytes are counted as read.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from app.aoi.errors import AoiValidationError

NESTED_ARCHIVE_SUFFIXES = (".zip", ".kmz", ".gz", ".tar", ".7z", ".rar", ".jar")


@dataclass
class SafeZip:
    zf: zipfile.ZipFile
    max_bytes: int
    read_total: int = field(default=0)

    def names(self) -> list[str]:
        return [i.filename for i in self.zf.infolist() if not i.is_dir()]

    def read(self, name: str) -> bytes:
        remaining = self.max_bytes - self.read_total
        with self.zf.open(name) as fh:
            data = fh.read(remaining + 1)
        self.read_total += len(data)
        if len(data) > remaining:
            raise AoiValidationError(
                "archive_too_large",
                "archive exceeds MAX_ARCHIVE_UNCOMPRESSED_MB when decompressed (zip bomb guard)",
                413,
            )
        return data


def open_safe_zip(data: bytes, max_files: int, max_uncompressed_mb: int) -> SafeZip:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise AoiValidationError("invalid_archive", "file is not a valid ZIP archive")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, NotImplementedError, OSError) as exc:
        raise AoiValidationError("invalid_archive", "archive could not be read") from exc
    if len(infos) > max_files:
        raise AoiValidationError(
            "archive_too_many_files",
            f"archive has {len(infos)} entries, exceeding MAX_ARCHIVE_FILES={max_files}",
        )
    declared = sum(i.file_size for i in infos)
    limit = max_uncompressed_mb * 1024 * 1024
    if declared > limit:
        raise AoiValidationError(
            "archive_too_large",
            f"archive declares {declared} bytes uncompressed, "
            f"exceeding MAX_ARCHIVE_UNCOMPRESSED_MB={max_uncompressed_mb}",
            413,
        )
    for i in infos:
        name = i.filename
        parts = name.replace("\\", "/").split("/")
        if (
            name.startswith(("/", "\\"))
            or ".." in parts
            or "\x00" in name
            or (len(name) > 1 and name[1] == ":")
        ):
            raise AoiValidationError("unsafe_archive_entry", "archive contains an unsafe path")
        if i.flag_bits & 0x1:
            raise AoiValidationError("encrypted_archive", "encrypted archives are not supported")
        if name.lower().endswith(NESTED_ARCHIVE_SUFFIXES):
            raise AoiValidationError("nested_archive", "nested archives are not supported")
    return SafeZip(zf, limit)
