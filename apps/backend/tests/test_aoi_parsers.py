"""Upload parsing and hostile-input tests (P2-04)."""

from __future__ import annotations

import json
import zipfile

import pytest
from aoi_helpers import (
    LIMITS,
    cw,
    feature,
    geojson_polygon,
    kml,
    make_zip,
    shapefile_zip,
    square_with_area,
)
from pyproj import Transformer

from app.aoi.archive import SafeZip, open_safe_zip
from app.aoi.errors import AoiValidationError
from app.aoi.geometry import build_polygon
from app.aoi.parsers import parse_upload, safe_filename

SQ = square_with_area(2.0)
MAX_FILES, MAX_MB = 50, 50


def parse(name: str, data: bytes):  # type: ignore[no-untyped-def]
    return parse_upload(name, data, MAX_FILES, MAX_MB)


def err(name: str, data: bytes, **kw: int) -> str:
    with pytest.raises(AoiValidationError) as e:
        parse_upload(name, data, kw.get("max_files", MAX_FILES), kw.get("max_mb", MAX_MB))
    return e.value.code


# ------------------------------------------------------------------ happy paths
@pytest.mark.parametrize(
    ("name", "data", "method"),
    [
        ("a.geojson", geojson_polygon(SQ), "geojson"),
        ("a.json", feature({"type": "Polygon", "coordinates": [SQ]}), "geojson"),
        (
            "a.geojson",
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [json.loads(feature({"type": "Polygon", "coordinates": [SQ]}))],
                }
            ).encode(),
            "geojson",
        ),
        ("a.geojson", feature({"type": "MultiPolygon", "coordinates": [[SQ]]}), "geojson"),
        ("a.kml", kml(SQ), "kml"),
        ("a.kmz", make_zip({"doc.kml": kml(SQ)}), "kmz"),
        ("a.kmz", make_zip({"other.kml": kml(SQ), "icon.png": b"x"}), "kmz"),
        ("a.zip", shapefile_zip([cw(SQ)]), "shapefile"),
    ],
)
def test_supported_formats_roundtrip_to_the_same_polygon(name: str, data: bytes, method: str) -> None:
    raw, m, details = parse(name, data)
    assert m == method and details["format"] == method
    g = build_polygon(raw, LIMITS)
    assert g.area_km2 == pytest.approx(2.0, rel=1e-3)


def test_geojson_with_bom_and_z() -> None:
    data = (
        b"\xef\xbb\xbf"
        + json.dumps({"type": "Polygon", "coordinates": [[[x, y, 5] for x, y in SQ]]}).encode()
    )
    raw, _, _ = parse("a.geojson", data)
    assert build_polygon(raw, LIMITS).area_km2 == pytest.approx(2.0, rel=1e-3)


def test_geojson_hole_is_kept() -> None:
    outer = square_with_area(4.0)
    x0, y0 = outer[0]
    s = outer[1][0] - x0
    hole = [[x0 + s * .4, y0 + s * .4], [x0 + s * .6, y0 + s * .4], [x0 + s * .6, y0 + s * .6], [x0 + s * .4, y0 + s * .6], [x0 + s * .4, y0 + s * .4]]  # fmt: skip
    raw, _, _ = parse("a.geojson", json.dumps({"type": "Polygon", "coordinates": [outer, hole]}).encode())
    assert len(raw.holes) == 1


def test_shapefile_in_utm_is_reprojected_to_wgs84() -> None:
    lon0, lat0 = 10.0, 50.0
    to_utm = Transformer.from_crs(4326, 32632, always_xy=True)
    corners = [(lon0, lat0), (lon0 + 0.02, lat0), (lon0 + 0.02, lat0 + 0.02), (lon0, lat0 + 0.02)]
    xy = [list(to_utm.transform(x, y)) for x, y in corners]
    xy.append(xy[0])
    from pyproj import CRS

    prj = CRS.from_epsg(32632).to_wkt()
    raw, _, details = parse("u.zip", shapefile_zip([cw(xy)], prj=prj))
    assert details["source_crs"]
    g = build_polygon(raw, LIMITS)
    minx, miny, maxx, maxy = g.bbox
    assert (minx, miny) == pytest.approx((lon0, lat0), abs=1e-6)
    assert (maxx, maxy) == pytest.approx((lon0 + 0.02, lat0 + 0.02), abs=1e-6)


# ------------------------------------------------------------------ rejections: content
@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("a.geojson", b"not json at all {", "file_type_mismatch"),
        ("a.geojson", b"{ broken", "invalid_geojson"),
        ("a.geojson", json.dumps([1, 2]).encode(), "file_type_mismatch"),
        ("a.geojson", feature({"type": "Point", "coordinates": [1, 2]}), "unsupported_geometry"),
        (
            "a.geojson",
            feature({"type": "LineString", "coordinates": [[1, 2], [3, 4]]}),
            "unsupported_geometry",
        ),
        (
            "a.geojson",
            json.dumps({"type": "GeometryCollection", "geometries": []}).encode(),
            "unsupported_geometry",
        ),
        (
            "a.geojson",
            feature({"type": "MultiPolygon", "coordinates": [[SQ], [SQ]]}),
            "multipart_unsupported",
        ),
        (
            "a.geojson",
            json.dumps({"type": "FeatureCollection", "features": []}).encode(),
            "not_single_feature",
        ),
        ("a.geojson", feature({"type": "Polygon", "coordinates": []}), "invalid_coordinate"),
        (
            "a.geojson",
            feature({"type": "Polygon", "coordinates": [[["a", 1], [2, 3], [4, 5]]]}),
            "invalid_coordinate",
        ),
        (
            "a.geojson",
            feature({"type": "Polygon", "coordinates": [[[True, 1], [2, 3], [4, 5]]]}),
            "invalid_coordinate",
        ),
        ("a.exe", b"MZ", "unsupported_file_type"),
        ("a", b"{}", "unsupported_file_type"),
        ("a.kml", b'{"type":"Polygon"}', "file_type_mismatch"),
        ("a.kmz", b"<kml/>", "file_type_mismatch"),
        ("a.zip", b"{}", "file_type_mismatch"),
    ],
)
def test_rejections(name: str, data: bytes, code: str) -> None:
    assert err(name, data) == code


def test_geojson_other_crs_rejected() -> None:
    doc = {
        "type": "Polygon",
        "coordinates": [SQ],
        "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
    }
    assert err("a.geojson", json.dumps(doc).encode()) == "unsupported_crs"
    doc["crs"]["properties"]["name"] = "urn:ogc:def:crs:OGC:1.3:CRS84"  # type: ignore[index]
    parse("a.geojson", json.dumps(doc).encode())


def test_kml_variants_rejected() -> None:
    assert (
        err(
            "a.kml",
            b"<kml><Document><Placemark><Point><coordinates>1,2</coordinates></Point></Placemark></Document></kml>",
        )
        == "no_polygon"
    )
    two = kml(
        SQ,
        extra=kml(SQ)
        .decode()
        .split("<Placemark>")[1]
        .split("</Placemark>")[0]
        .join(["<Placemark>", "</Placemark>"]),
    )
    assert err("a.kml", two) == "multipart_unsupported"
    assert err("a.kml", b"<kml><oops") == "invalid_kml"
    bad = kml(SQ).replace(b"<coordinates>", b"<coordinates>x,y,z ")
    assert err("a.kml", bad) == "invalid_coordinate"
    assert err("a.kml", b"<kml><Polygon></Polygon></kml>") == "invalid_kml"


def test_kml_xxe_and_entity_bombs_are_refused() -> None:
    xxe = b'<?xml version="1.0"?><!DOCTYPE k [<!ENTITY x SYSTEM "file:///etc/passwd">]><kml><n>&x;</n></kml>'
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
        b'<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><kml><n>&c;</n></kml>'
    )
    assert err("a.kml", xxe) == "xml_forbidden"
    assert err("a.kml", bomb) == "xml_forbidden"


def test_shapefile_rejections() -> None:
    assert err("a.zip", shapefile_zip([cw(SQ)], prj=None)) == "missing_prj"
    assert err("a.zip", shapefile_zip([cw(SQ)], features=2)) == "not_single_feature"
    assert err("a.zip", shapefile_zip([cw(SQ)], prj="garbage not wkt")) == "unsupported_crs"
    assert err("a.zip", make_zip({"a.txt": b"hello"})) == "invalid_shapefile"
    assert err(
        "a.zip", make_zip({"a.shp": b"junk", "a.prj": shapefile_zip([cw(SQ)]).__len__().__str__().encode()})
    ) in ("unsupported_crs", "invalid_shapefile")
    assert err("a.zip", make_zip({"a.shp": b"junk", "b.shp": b"junk"})) == "invalid_shapefile"


# ------------------------------------------------------------------ hostile archives
def test_zip_bomb_declared_size() -> None:
    bomb = make_zip({"doc.kml": b"0" * (3 * 1024 * 1024)})
    assert len(bomb) < 20_000  # tiny on the wire
    assert err("a.kmz", bomb, max_mb=1) == "archive_too_large"


def test_zip_bomb_actual_read_cap_does_not_trust_declared_sizes() -> None:
    data = make_zip({"doc.kml": b"0" * (2 * 1024 * 1024)})
    zf = zipfile.ZipFile(__import__("io").BytesIO(data))
    sz = SafeZip(zf, max_bytes=1024 * 1024)  # pretend the header lied: budget is enforced on bytes read
    with pytest.raises(AoiValidationError) as e:
        sz.read("doc.kml")
    assert e.value.code == "archive_too_large" and e.value.status == 413


def test_read_budget_is_shared_across_members() -> None:
    data = make_zip({"a": b"1" * 700_000, "b": b"2" * 700_000})
    sz = SafeZip(zipfile.ZipFile(__import__("io").BytesIO(data)), max_bytes=1_000_000)
    sz.read("a")
    with pytest.raises(AoiValidationError):
        sz.read("b")


@pytest.mark.parametrize(
    "name", ["../evil.kml", "/abs/evil.kml", "a/../../evil.kml", "C:/evil.kml", "..\\evil.kml"]
)
def test_traversal_entry_names_rejected(name: str) -> None:
    assert err("a.kmz", make_zip({name: kml(SQ)})) == "unsafe_archive_entry"


def test_too_many_files() -> None:
    files = {f"f{i}.txt": b"x" for i in range(60)}
    files["doc.kml"] = kml(SQ)
    assert err("a.kmz", make_zip(files)) == "archive_too_many_files"
    assert (
        err("a.kmz", make_zip({"doc.kml": kml(SQ), "x.txt": b"1", "y.txt": b"2"}), max_files=2)
        == "archive_too_many_files"
    )


def test_nested_archives_rejected() -> None:
    assert (
        err("a.kmz", make_zip({"doc.kml": kml(SQ), "inner.zip": make_zip({"x": b"1"})})) == "nested_archive"
    )


def test_encrypted_entries_rejected() -> None:
    buf = __import__("io").BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zi = zipfile.ZipInfo("doc.kml")
        zf.writestr(zi, kml(SQ))
    raw = bytearray(buf.getvalue())
    # set general-purpose bit 0 (encrypted) in both local header (offset 6) and central directory entry
    raw[6] |= 1
    cd = raw.rfind(b"PK\x01\x02")
    raw[cd + 8] |= 1
    assert err("a.kmz", bytes(raw)) == "encrypted_archive"


def test_corrupt_zip_and_empty_kmz() -> None:
    assert err("a.kmz", b"PK\x03\x04garbage-garbage-garbage") == "invalid_archive"
    assert err("a.kmz", make_zip({"readme.txt": b"hi"})) == "invalid_kmz"
    assert err("a.kmz", make_zip({"a.kml": kml(SQ), "b.kml": kml(SQ)})) == "invalid_kmz"


def test_open_safe_zip_rejects_non_zip() -> None:
    with pytest.raises(AoiValidationError):
        open_safe_zip(b"hello", 10, 10)


# ------------------------------------------------------------------ misc
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.geojson", "passwd.geojson"),
        ("C:\\Users\\x\\a b.kml", "a b.kml"),
        ("na\x00me\n.kml", "na_me_.kml"),
        ("", "upload"),
        ("x" * 300 + ".kml", ("x" * 300 + ".kml")[:100]),
    ],
)
def test_safe_filename(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected
