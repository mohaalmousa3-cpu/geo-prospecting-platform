"""Boundary tests for the upload / archive limits (ADR-0008 values, semantics from ADR-0012 §8).

Documented semantics (ADR-0012 §8): reject an upload *larger than* ``MAX_UPLOAD_MB``; reject an archive with
*more than* ``MAX_ARCHIVE_FILES`` entries; reject an archive exceeding ``MAX_ARCHIVE_UNCOMPRESSED_MB`` in
uncompressed bytes (declared sizes are not trusted: bytes are counted as read). A value exactly at the limit is
therefore accepted. Each limit is tested just below, exactly at, and just above, with the limit lowered through
settings so the fixtures stay small. Production defaults are not touched.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from aoi_helpers import cw, kml, make_zip, shapefile_zip, square_with_area
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.aoi.archive import SafeZip
from app.aoi.errors import AoiValidationError
from app.aoi.parsers import parse_upload
from app.main import create_app
from geo_common.config import Settings

MIB = 1024 * 1024
SQ = square_with_area(2.0)


def _padded(payload: bytes, total: int, pad: bytes = b" ") -> bytes:
    """Append whitespace after the document (valid for JSON and XML) until it is exactly ``total`` bytes."""
    assert len(payload) <= total, (len(payload), total)
    return payload + pad * (total - len(payload))


def _geojson(total: int) -> bytes:
    import json

    return _padded(json.dumps({"type": "Polygon", "coordinates": [SQ]}).encode(), total)


def _upload_code(name: str, data: bytes, max_files: int = 50, max_mb: int = 50) -> str:
    try:
        parse_upload(name, data, max_files, max_mb)
    except AoiValidationError as exc:
        return exc.code
    return "ok"


# ------------------------------------------------------------------ archive entry count (no database)
@pytest.mark.parametrize(
    ("limit", "entries", "expected"), [(5, 4, "ok"), (5, 5, "ok"), (5, 6, "archive_too_many_files")]
)
def test_kmz_entry_count_boundary(limit: int, entries: int, expected: str) -> None:
    files = {"doc.kml": kml(SQ)} | {f"img{i}.png": b"x" for i in range(entries - 1)}
    assert len(files) == entries
    assert _upload_code("a.kmz", make_zip(files), max_files=limit) == expected


@pytest.mark.parametrize(("limit", "expected"), [(5, "ok"), (4, "ok"), (3, "archive_too_many_files")])
def test_shapefile_zip_entry_count_boundary(limit: int, expected: str) -> None:
    data = shapefile_zip([cw(SQ)])  # .shp .shx .dbf .prj = 4 entries
    assert len(zipfile.ZipFile(io.BytesIO(data)).infolist()) == 4
    assert _upload_code("a.zip", data, max_files=limit) == expected


# ------------------------------------------------------------------ archive uncompressed size (no database)
@pytest.mark.parametrize(
    ("total", "expected"), [(MIB - 1, "ok"), (MIB, "ok"), (MIB + 1, "archive_too_large")]
)
def test_kmz_uncompressed_size_boundary_single_member(total: int, expected: str) -> None:
    data = make_zip({"doc.kml": _padded(kml(SQ), total)})
    assert (
        len(data) < MIB
    )  # compressed upload is far below MAX_UPLOAD_MB: only the archive limit is exercised
    assert _upload_code("a.kmz", data, max_mb=1) == expected


@pytest.mark.parametrize(
    ("total", "expected"), [(MIB - 1, "ok"), (MIB, "ok"), (MIB + 1, "archive_too_large")]
)
def test_kmz_uncompressed_size_boundary_sums_all_members(total: int, expected: str) -> None:
    doc = kml(SQ)
    data = make_zip({"doc.kml": doc, "pad.bin": b"\0" * (total - len(doc))})
    assert _upload_code("a.kmz", data, max_mb=1) == expected


@pytest.mark.parametrize(("total", "expected"), [(99, "ok"), (100, "ok"), (101, "archive_too_large")])
def test_actual_read_bytes_boundary(total: int, expected: str) -> None:
    """The read budget counts bytes actually read (cumulative across members), independent of declared sizes."""
    data = make_zip({"a": b"1" * 60, "b": b"2" * (total - 60)})
    sz = SafeZip(zipfile.ZipFile(io.BytesIO(data)), max_bytes=100)
    try:
        sz.read("a")
        sz.read("b")
    except AoiValidationError as exc:
        assert exc.code == expected
    else:
        assert expected == "ok"
        assert sz.read_total == total


# ------------------------------------------------------------------ upload size through the API (PostGIS)
def _client(engine: Engine, **overrides: object) -> TestClient:
    s = Settings(_env_file=None, CORS_ALLOWED_ORIGINS="http://localhost:3000", **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(s, engine=engine))


def _project(c: TestClient) -> str:
    return c.post("/api/v1/projects", json={"name": "limits"}).json()["id"]


@pytest.mark.integration
@pytest.mark.parametrize(("total", "status"), [(MIB - 1, 201), (MIB, 201), (MIB + 1, 413)])
def test_upload_size_boundary_via_api(engine: Engine, total: int, status: int) -> None:
    with _client(engine, MAX_UPLOAD_MB=1) as c:
        r = c.post(
            "/api/v1/aois/upload",
            files={"file": ("site.geojson", _geojson(total))},
            data={"project_id": _project(c)},
        )
        assert r.status_code == status, r.text
        if status == 413:
            assert r.json()["error"]["code"] == "payload_too_large"
            assert c.get("/api/v1/aois").json()["total"] == 0
        else:
            assert c.get("/api/v1/aois").json()["total"] == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("entries", "status", "code"),
    [(4, 201, None), (5, 201, None), (6, 422, "archive_too_many_files")],
)
def test_archive_entry_count_boundary_via_api(
    engine: Engine, entries: int, status: int, code: str | None
) -> None:
    files = {"doc.kml": kml(SQ)} | {f"img{i}.png": b"x" for i in range(entries - 1)}
    with _client(engine, MAX_ARCHIVE_FILES=5) as c:
        r = c.post(
            "/api/v1/aois/upload",
            files={"file": ("site.kmz", make_zip(files))},
            data={"project_id": _project(c)},
        )
        assert r.status_code == status, r.text
        if code:
            assert r.json()["error"]["code"] == code


@pytest.mark.integration
@pytest.mark.parametrize(
    ("total", "status", "code"),
    [(MIB - 1, 201, None), (MIB, 201, None), (MIB + 1, 413, "archive_too_large")],
)
def test_archive_uncompressed_boundary_via_api(
    engine: Engine, total: int, status: int, code: str | None
) -> None:
    with _client(engine, MAX_ARCHIVE_UNCOMPRESSED_MB=1) as c:
        r = c.post(
            "/api/v1/aois/upload",
            files={"file": ("site.kmz", make_zip({"doc.kml": _padded(kml(SQ), total)}))},
            data={"project_id": _project(c)},
        )
        assert r.status_code == status, r.text
        if code:
            assert r.json()["error"]["code"] == code
