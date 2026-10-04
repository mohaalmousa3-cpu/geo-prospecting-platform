"""Projects (Phase 2.5): CRUD, ownership of AOIs, deletion rules, limits. Bookkeeping only."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aoi_helpers import cw, geojson_polygon, shapefile_zip, square_with_area
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.main import create_app
from geo_common.config import Settings

pytestmark = pytest.mark.integration
SQ = square_with_area(2.0)
RECT = {"method": "rectangle", "name": "rect", "west": 10.0, "south": 0.0, "east": 10.02, "north": 0.02}


def mk(client: TestClient, name: str = "Proj", **kw: object) -> dict:  # type: ignore[type-arg]
    r = client.post("/api/v1/projects", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def aoi(client: TestClient, pid: str, **kw: object) -> dict:  # type: ignore[type-arg]
    r = client.post("/api/v1/aois", json={**RECT, "project_id": pid, **kw})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_create_get_list_roundtrip(client: TestClient) -> None:
    p = mk(client, "  Site survey  ", description=" first pilot ")
    assert p["name"] == "Site survey" and p["description"] == "first pilot" and p["aoi_count"] == 0
    assert client.get(f"/api/v1/projects/{p['id']}").json() == p
    mk(client, "second")
    lst = client.get("/api/v1/projects").json()
    assert lst["total"] == 2 and [i["name"] for i in lst["items"]] == [
        "Site survey",
        "second",
    ]  # oldest first


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": ""}, "validation_error"),
        ({"name": "   "}, "name_required"),
        ({"name": "x" * 121}, "validation_error"),
        ({"name": "ok", "description": "d" * 501}, "validation_error"),
        ({}, "validation_error"),
        ({"name": "ok", "owner": "me"}, "validation_error"),
    ],
)
def test_invalid_project_requests(client: TestClient, body: dict[str, object], code: str) -> None:
    r = client.post("/api/v1/projects", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert client.get("/api/v1/projects").json()["total"] == 0


def test_project_limit_is_409(engine: Engine) -> None:
    s = Settings(_env_file=None, MAX_PROJECTS=2)
    with TestClient(create_app(s, engine=engine)) as c:
        mk(c, "a")
        mk(c, "b")
        r = c.post("/api/v1/projects", json={"name": "c"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "project_limit_reached"
        assert "MAX_PROJECTS=2" in r.json()["error"]["message"]


def test_unknown_and_malformed_project_ids(client: TestClient) -> None:
    assert client.get(f"/api/v1/projects/{uuid4()}").json()["error"]["code"] == "project_not_found"
    assert client.delete(f"/api/v1/projects/{uuid4()}").status_code == 404
    assert client.get("/api/v1/projects/nope").status_code == 422


# ---------------------------------------------------------------- AOIs belong to projects
def test_saving_an_aoi_requires_a_project(client: TestClient) -> None:
    r = client.post("/api/v1/aois", json=RECT)
    assert r.status_code == 422 and r.json()["error"]["code"] == "project_required"
    r = client.post("/api/v1/aois", json={**RECT, "project_id": str(uuid4())})
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"
    r = client.post("/api/v1/aois", json={**RECT, "project_id": "not-a-uuid"})
    assert r.status_code == 422
    assert client.get("/api/v1/aois").json()["total"] == 0


def test_preview_needs_no_project_and_validation_is_unchanged(client: TestClient) -> None:
    assert client.post("/api/v1/aois/preview", json=RECT).status_code == 200
    bad = client.post("/api/v1/aois/preview", json={**RECT, "east": 12.0, "north": 2.0})
    assert bad.json()["error"]["code"] == "area_too_large"
    # a valid project does not relax validation on save either
    p = mk(client)
    r = client.post("/api/v1/aois", json={**RECT, "east": 12.0, "north": 2.0, "project_id": p["id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "area_too_large"
    assert client.get(f"/api/v1/projects/{p['id']}").json()["aoi_count"] == 0


def test_aoi_carries_its_project_and_counts_update(client: TestClient) -> None:
    a, b = mk(client, "A"), mk(client, "B")
    x = aoi(client, a["id"], name="x")
    aoi(client, a["id"], name="y")
    aoi(client, b["id"], name="z")
    assert x["project_id"] == a["id"]
    assert client.get(f"/api/v1/aois/{x['id']}").json()["project_id"] == a["id"]
    counts = {p["name"]: p["aoi_count"] for p in client.get("/api/v1/projects").json()["items"]}
    assert counts == {"A": 2, "B": 1}


def test_list_aois_filters_by_project(client: TestClient) -> None:
    a, b = mk(client, "A"), mk(client, "B")
    for n in ("a1", "a2"):
        aoi(client, a["id"], name=n)
    aoi(client, b["id"], name="b1")
    assert client.get("/api/v1/aois").json()["total"] == 3
    fa = client.get("/api/v1/aois", params={"project_id": a["id"]}).json()
    assert fa["total"] == 2 and {i["name"] for i in fa["items"]} == {"a1", "a2"}
    assert all(i["project_id"] == a["id"] for i in fa["items"])
    assert client.get("/api/v1/aois", params={"project_id": str(uuid4())}).json()["total"] == 0


def test_upload_saves_into_the_given_project_and_requires_it(client: TestClient) -> None:
    p = mk(client)
    files = {"file": ("s.geojson", geojson_polygon(SQ))}
    ok = client.post("/api/v1/aois/upload", files=files, data={"project_id": p["id"]})
    assert ok.status_code == 201 and ok.json()["project_id"] == p["id"]
    missing = client.post("/api/v1/aois/upload", files=files)
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "project_required"
    unknown = client.post("/api/v1/aois/upload", files=files, data={"project_id": str(uuid4())})
    assert unknown.status_code == 404
    preview = client.post("/api/v1/aois/upload", files=files, params={"preview": "true"})
    assert preview.status_code == 200  # preview needs no project
    zipped = {"file": ("s.zip", shapefile_zip([cw(SQ)]))}
    assert client.post("/api/v1/aois/upload", files=zipped, data={"project_id": p["id"]}).status_code == 201


def test_hostile_upload_is_still_rejected_with_a_valid_project(client: TestClient) -> None:
    p = mk(client)
    r = client.post(
        "/api/v1/aois/upload",
        files={"file": ("x.kml", b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><kml>&e;</kml>')},
        data={"project_id": p["id"]},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "xml_forbidden"
    assert client.get(f"/api/v1/projects/{p['id']}").json()["aoi_count"] == 0


# ---------------------------------------------------------------- deletion rules
def test_delete_empty_project(client: TestClient) -> None:
    p = mk(client)
    assert client.delete(f"/api/v1/projects/{p['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{p['id']}").status_code == 404


def test_delete_refuses_a_non_empty_project_unless_asked(client: TestClient) -> None:
    p = mk(client)
    a = aoi(client, p["id"])
    r = client.delete(f"/api/v1/projects/{p['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_not_empty"
    assert "1 AOI" in r.json()["error"]["message"]
    assert client.get(f"/api/v1/aois/{a['id']}").status_code == 200  # nothing was removed
    assert client.delete(f"/api/v1/projects/{p['id']}", params={"delete_aois": "true"}).status_code == 204
    assert client.get(f"/api/v1/aois/{a['id']}").status_code == 404
    assert client.get("/api/v1/projects").json()["total"] == 0


def test_deleting_one_project_leaves_others_untouched(client: TestClient) -> None:
    a, b = mk(client, "A"), mk(client, "B")
    keep = aoi(client, b["id"])
    aoi(client, a["id"])
    client.delete(f"/api/v1/projects/{a['id']}", params={"delete_aois": "true"})
    assert client.get(f"/api/v1/aois/{keep['id']}").status_code == 200
    assert client.get("/api/v1/aois").json()["total"] == 1


def test_deleting_an_aoi_does_not_delete_its_project(client: TestClient) -> None:
    p = mk(client)
    a = aoi(client, p["id"])
    assert client.delete(f"/api/v1/aois/{a['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{p['id']}").json()["aoi_count"] == 0


def test_aoi_storage_limit_is_still_global(engine: Engine) -> None:
    s = Settings(_env_file=None, MAX_STORED_AOIS=1)
    with TestClient(create_app(s, engine=engine)) as c:
        a, b = mk(c, "A"), mk(c, "B")
        aoi(c, a["id"])
        r = c.post("/api/v1/aois", json={**RECT, "project_id": b["id"]})
        assert r.status_code == 409 and r.json()["error"]["code"] == "aoi_limit_reached"


def test_project_payloads_carry_no_analysis_fields(client: TestClient) -> None:
    p = mk(client)
    keys = " ".join(p).lower() + " " + " ".join(client.get("/api/v1/aois/limits").json()).lower()
    assert not any(
        k in keys for k in ("score", "prospectiv", "anomaly", "confidence", "target", "rank", "depth")
    )


def test_concurrent_project_creation_respects_the_limit(engine: Engine) -> None:
    from concurrent.futures import ThreadPoolExecutor

    s = Settings(_env_file=None, MAX_PROJECTS=3)
    with TestClient(create_app(s, engine=engine)) as c:
        with ThreadPoolExecutor(8) as ex:
            codes = list(
                ex.map(lambda i: c.post("/api/v1/projects", json={"name": f"p{i}"}).status_code, range(12))
            )
    assert codes.count(201) == 3 and codes.count(409) == 9
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM project")).scalar_one() == 3
