from __future__ import annotations

import json
from uuid import uuid4

import pytest
from aoi_helpers import cw, feature, geojson_polygon, kml, make_zip, shapefile_zip, square_with_area
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.main import create_app
from geo_common.config import Settings

pytestmark = pytest.mark.integration
SQ = square_with_area(2.0)
PR = {"method": "point_radius", "name": "circle", "lat": 12.5, "lon": 40.1, "radius_m": 1500}
RECT = {"method": "rectangle", "name": "rect", "west": 10.0, "south": 0.0, "east": 10.02, "north": 0.02}
POLY = {"method": "polygon", "name": "poly", "coordinates": [[c[0], c[1]] for c in SQ[:-1]]}
ANALYSIS_KEYS = ("score", "prospectiv", "anomaly", "confidence", "target", "rank", "depth", "gold", "void")


def client_with(engine: Engine, **overrides: object) -> TestClient:
    s = Settings(_env_file=None, CORS_ALLOWED_ORIGINS="http://localhost:3000", **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(s, engine=engine))


def test_limits_endpoint_reports_adr_0008_defaults(client: TestClient) -> None:
    lim = client.get("/api/v1/aois/limits").json()
    assert lim["max_area_km2"] == 25 and lim["max_radius_m"] == 2500 and lim["min_area_km2"] == 0.01
    assert lim["max_abs_latitude"] == 85 and "kmz" in lim["supported_upload_formats"]


@pytest.mark.parametrize("body", [PR, RECT, POLY])
def test_preview_does_not_persist(client: TestClient, body: dict[str, object], engine: Engine) -> None:
    r = client.post("/api/v1/aois/preview", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["geometry"]["type"] == "Polygon" and d["area_km2"] > 0 and d["working_crs"].startswith("EPSG:32")
    assert "id" not in d
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM aoi")).scalar_one() == 0


@pytest.mark.parametrize("body", [PR, RECT, POLY])
def test_create_get_list_delete_roundtrip(client: TestClient, body: dict[str, object]) -> None:
    created = client.post("/api/v1/aois", json=body)
    assert created.status_code == 201, created.text
    aoi = created.json()
    assert aoi["name"] == body["name"] and aoi["method"] == body["method"]
    got = client.get(f"/api/v1/aois/{aoi['id']}").json()
    assert got["geometry"] == aoi["geometry"]  # persisted geometry == returned geometry
    assert got["area_km2"] == pytest.approx(aoi["area_km2"]) and got["bbox"] == pytest.approx(aoi["bbox"])
    lst = client.get("/api/v1/aois").json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == aoi["id"] and "geometry" not in lst["items"][0]
    assert client.delete(f"/api/v1/aois/{aoi['id']}").status_code == 204
    assert client.get(f"/api/v1/aois/{aoi['id']}").status_code == 404
    assert client.delete(f"/api/v1/aois/{aoi['id']}").status_code == 404


def test_point_radius_details_and_polygon_is_valid_in_postgis(client: TestClient, engine: Engine) -> None:
    aoi = client.post("/api/v1/aois", json=PR).json()
    assert aoi["details"] == {"lat": 12.5, "lon": 40.1, "radius_m": 1500, "circle_vertices": 72}
    with engine.connect() as c:
        row = c.execute(text("SELECT ST_IsValid(geom), ST_SRID(geom), ST_GeometryType(geom) FROM aoi")).one()
    assert tuple(row) == (True, 4326, "ST_Polygon")


def test_open_ring_warning_is_returned(client: TestClient) -> None:
    d = client.post("/api/v1/aois/preview", json=POLY).json()
    assert any("closed automatically" in w for w in d["warnings"])


def test_name_rules(client: TestClient) -> None:
    no_name = {k: v for k, v in RECT.items() if k != "name"}
    assert client.post("/api/v1/aois", json=no_name).json()["error"]["code"] == "name_required"
    assert client.post("/api/v1/aois", json={**RECT, "name": "x" * 121}).status_code == 422
    assert client.post("/api/v1/aois", json={**RECT, "name": ""}).status_code == 422
    assert client.post("/api/v1/aois/preview", json=no_name).status_code == 200  # preview needs no name


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({**PR, "radius_m": 2500.01}, 422, "radius_too_large"),
        ({**PR, "radius_m": 0}, 422, "invalid_radius"),
        ({**PR, "lat": 91}, 422, "coordinate_out_of_range"),
        ({**PR, "lat": 86}, 422, "latitude_unsupported"),
        ({**PR, "lon": 179.99}, 422, "antimeridian_unsupported"),
        ({**RECT, "west": 11}, 422, "invalid_rectangle"),
        ({**RECT, "east": 10.8, "north": 0.8}, 422, "area_too_large"),
        ({**RECT, "east": 10.00001, "north": 0.00001}, 422, "area_too_small"),
        ({**POLY, "coordinates": [[10, 0], [10.1, 0.1], [10.1, 0], [10, 0.1]]}, 422, "invalid_geometry"),
        ({**POLY, "coordinates": [[10, 0], [11, 0]]}, 422, "validation_error"),
        ({"method": "circle", "lat": 1}, 422, "validation_error"),
        ({**PR, "extra": 1}, 422, "validation_error"),
        ({**PR, "lat": "north"}, 422, "validation_error"),
    ],
)
def test_validation_errors_are_specific(
    client: TestClient, body: dict[str, object], status: int, code: str
) -> None:
    r = client.post("/api/v1/aois", json=body)
    assert r.status_code == status and r.json()["error"]["code"] == code, r.text
    assert client.get("/api/v1/aois").json()["total"] == 0  # nothing persisted on rejection


def test_nan_and_infinity_json_are_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/v1/aois",
        content=b'{"method":"point_radius","lat":NaN,"lon":1,"radius_m":10}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_storage_limit_returns_409(engine: Engine) -> None:
    with client_with(engine, MAX_STORED_AOIS=2) as c:
        assert c.post("/api/v1/aois", json=RECT).status_code == 201
        assert c.post("/api/v1/aois", json=RECT).status_code == 201
        r = c.post("/api/v1/aois", json=RECT)
        assert r.status_code == 409 and r.json()["error"]["code"] == "aoi_limit_reached"
        assert "MAX_STORED_AOIS=2" in r.json()["error"]["message"]


def test_list_pagination_and_order(client: TestClient) -> None:
    ids = [client.post("/api/v1/aois", json={**RECT, "name": f"a{i}"}).json()["id"] for i in range(3)]
    page = client.get("/api/v1/aois", params={"limit": 2}).json()
    assert page["total"] == 3 and [i["id"] for i in page["items"]] == ids[::-1][:2]
    assert [
        i["id"] for i in client.get("/api/v1/aois", params={"limit": 2, "offset": 2}).json()["items"]
    ] == ids[:1]
    assert client.get("/api/v1/aois", params={"limit": 101}).status_code == 422


def test_malformed_ids(client: TestClient) -> None:
    assert client.get("/api/v1/aois/nope").status_code == 422
    assert client.get(f"/api/v1/aois/{uuid4()}").status_code == 404


# ------------------------------------------------------------------ uploads
def up(client: TestClient, name: str, data: bytes, **kw: object):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/aois/upload", files={"file": (name, data)}, **kw)


@pytest.mark.parametrize(
    ("name", "data", "method"),
    [
        ("site.geojson", geojson_polygon(SQ), "geojson"),
        ("site.kml", kml(SQ), "kml"),
        ("site.kmz", make_zip({"doc.kml": kml(SQ)}), "kmz"),
        ("site.zip", shapefile_zip([cw(SQ)]), "shapefile"),
    ],
)
def test_upload_all_formats(client: TestClient, name: str, data: bytes, method: str) -> None:
    r = up(client, name, data)
    assert r.status_code == 201, r.text
    aoi = r.json()
    assert aoi["method"] == method and aoi["name"] == "site" and aoi["details"]["filename"] == name
    assert aoi["area_km2"] == pytest.approx(2.0, rel=1e-3)


def test_upload_name_and_preview(client: TestClient, engine: Engine) -> None:
    r = client.post(
        "/api/v1/aois/upload",
        params={"preview": "true"},
        files={"file": ("p.geojson", geojson_polygon(SQ))},
        data={"name": "ignored"},
    )
    assert r.status_code == 200 and "id" not in r.json()
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM aoi")).scalar_one() == 0
    named = client.post(
        "/api/v1/aois/upload", files={"file": ("p.geojson", geojson_polygon(SQ))}, data={"name": "My site"}
    )
    assert named.json()["name"] == "My site"


def test_upload_filename_is_sanitised(client: TestClient) -> None:
    r = up(client, "../../etc/passwd/../x.geojson", geojson_polygon(SQ))
    assert r.status_code == 201 and r.json()["details"]["filename"] == "x.geojson"


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("a.geojson", feature({"type": "Point", "coordinates": [1, 2]}), 422, "unsupported_geometry"),
        ("a.exe", b"MZ\x90", 422, "unsupported_file_type"),
        (
            "a.kml",
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><kml>&e;</kml>',
            422,
            "xml_forbidden",
        ),
        ("a.zip", shapefile_zip([cw(SQ)], prj=None), 422, "missing_prj"),
        ("a.kmz", make_zip({"../x.kml": kml(SQ)}), 422, "unsafe_archive_entry"),
        ("a.geojson", b"", 422, "empty_file"),
        ("a.geojson", geojson_polygon(square_with_area(40.0)), 422, "area_too_large"),
    ],
)
def test_hostile_or_invalid_uploads(
    client: TestClient, name: str, data: bytes, status: int, code: str
) -> None:
    r = up(client, name, data)
    assert r.status_code == status and r.json()["error"]["code"] == code, r.text
    assert client.get("/api/v1/aois").json()["total"] == 0


def test_oversize_upload_is_413(engine: Engine) -> None:
    with client_with(engine, MAX_UPLOAD_MB=1) as c:
        big = json.dumps({"type": "Polygon", "coordinates": [SQ], "pad": "x" * (1024 * 1024 + 10)}).encode()
        r = up(c, "big.geojson", big)
        assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_zip_bomb_upload_is_rejected_via_api(engine: Engine) -> None:
    with client_with(engine, MAX_ARCHIVE_UNCOMPRESSED_MB=1) as c:
        r = up(c, "bomb.kmz", make_zip({"doc.kml": b"0" * (3 * 1024 * 1024)}))
        assert r.status_code == 413 and r.json()["error"]["code"] == "archive_too_large"


# ------------------------------------------------------------------ scope guard
def test_aoi_responses_carry_no_analysis_fields(client: TestClient) -> None:
    aoi = client.post("/api/v1/aois", json=PR).json()
    for payload in (
        aoi,
        client.get("/api/v1/aois").json()["items"][0],
        client.get("/api/v1/aois/limits").json(),
    ):
        keys = " ".join(payload).lower()
        assert not any(k in keys for k in ANALYSIS_KEYS), keys
