"""GET /connectors (fixture-only capability) and GET /aois/{id}/assets (isolation, ordering, pagination)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.main import create_app
from geo_common.config import Settings
from geo_common.storage import LocalStorage

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]


def app_with(engine: Engine, mode: str) -> TestClient:
    s = Settings(_env_file=None, CONNECTOR_MODE=mode, CORS_ALLOWED_ORIGINS="http://localhost:3000")  # type: ignore[call-arg]
    return TestClient(create_app(s, engine=engine))


# ------------------------------------------------------------------ GET /connectors
@pytest.mark.parametrize(("mode", "enabled"), [("disabled", False), ("fixture", True), ("live", False)])
def test_connectors_reports_fixture_only_capability_in_every_mode(
    engine: Engine, mode: str, enabled: bool
) -> None:
    body = app_with(engine, mode).get("/api/v1/connectors").json()
    assert body["mode"] == mode and body["live_available"] is False
    assert body["connectors"] == [
        {"name": "fixture", "kind": "fixture", "enabled": enabled, "synthetic": True,
         "job_types": ["catalog_search"], "asset_kinds": ["scene_catalog"]}
    ]  # fmt: skip


def test_connectors_discloses_and_accepts_no_host_url_or_credential(engine: Engine) -> None:
    c = app_with(engine, "live")
    plain = c.get("/api/v1/connectors")
    probed = c.get("/api/v1/connectors?host=evil.example&url=http://x&token=t&provider=stac")
    assert probed.json() == plain.json()  # query input has no effect
    flat = json.dumps(plain.json()).lower()
    for word in ("http", "host", "url", "token", "password", "secret", "endpoint", "port"):
        assert word not in flat, word
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/v1/connectors").status_code == 405


def test_the_static_description_matches_the_connector_registry_and_the_handler() -> None:
    from geo_connectors.handler import KIND
    from geo_connectors.registry import default_registry

    assert default_registry().names() == ["fixture"]
    assert KIND == "scene_catalog"


# ------------------------------------------------------------------ GET /aois/{id}/assets
@pytest.fixture
def api(client: TestClient, storage: LocalStorage) -> TestClient:
    client.app.state.storage = storage  # type: ignore[attr-defined]
    return client


def test_only_the_assets_of_that_aoi_are_listed_across_projects_and_siblings(
    api: TestClient, make_aoi: MakeAoi, add_job: AddJob, assets: Any
) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi(p)  # sibling AOI of the same project
    _, a3 = make_aoi()  # another project
    mine = [assets.add(a1)[0] for _ in range(3)]
    assets.add(a2)
    assets.add(a3)
    body = api.get(f"/api/v1/aois/{a1}/assets").json()
    assert body["total"] == 3 and {i["id"] for i in body["items"]} == {str(i) for i in mine}
    assert {i["aoi_id"] for i in body["items"]} == {str(a1)} and {i["project_id"] for i in body["items"]} == {
        str(p)
    }
    # a job id of another AOI can only narrow to nothing, never widen
    other_job = add_job(a2, "succeeded")
    assert api.get(f"/api/v1/aois/{a1}/assets?job_id={other_job}").json() == {"items": [], "total": 0}


def test_ordering_pagination_and_the_job_filter(
    api: TestClient, make_aoi: MakeAoi, add_job: AddJob, assets: Any
) -> None:
    _, a = make_aoi()
    job = add_job(a, "succeeded")
    ids = [str(assets.add(a, job if i == 0 else None)[0]) for i in range(5)]
    full = api.get(f"/api/v1/aois/{a}/assets").json()
    assert [i["id"] for i in full["items"]] == ids  # created_at, id: oldest first
    page = api.get(f"/api/v1/aois/{a}/assets?limit=2&offset=2").json()
    assert page["total"] == 5 and [i["id"] for i in page["items"]] == ids[2:4]
    assert [i["id"] for i in api.get(f"/api/v1/aois/{a}/assets?job_id={job}").json()["items"]] == ids[:1]
    assert api.get(f"/api/v1/aois/{a}/assets?limit=0").status_code == 422
    assert api.get(f"/api/v1/aois/{a}/assets?limit=101").status_code == 422
    assert api.get(f"/api/v1/aois/{a}/assets?offset=-1").status_code == 422


def test_unknown_aoi_is_404_and_a_path_is_never_interpreted(
    api: TestClient, make_aoi: MakeAoi, assets: Any
) -> None:
    _, a = make_aoi()
    _, key = assets.add(a)
    r = api.get(f"/api/v1/aois/{uuid.uuid4()}/assets")
    assert r.status_code == 404 and r.json()["error"]["code"] == "aoi_not_found"
    # (raw dot-segments are normalised by the HTTP client before they reach the server, so they prove nothing)
    for bad in ("..%2F..%2Fetc", "projects", key.replace("/", "%2F"), f"{a}%2F..%2F{a}", "x" * 40):
        assert api.get(f"/api/v1/aois/{bad}/assets").status_code in (404, 422), bad
    for bad in ("../x", key, "/etc/passwd"):  # job_id is a UUID; any path-like value is refused
        assert api.get(f"/api/v1/aois/{a}/assets", params={"job_id": bad}).status_code == 422, bad
    body = json.dumps(api.get(f"/api/v1/aois/{a}/assets").json())
    assert key not in body and "storage_key" not in body and "projects/" not in body  # no filesystem location
