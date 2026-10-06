"""Asset endpoints: read, content, delete (new response contract), and what the API must not offer."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from geo_common.storage import LocalStorage

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]


@pytest.fixture
def api(client: TestClient, storage: LocalStorage) -> TestClient:
    client.app.state.storage = storage  # type: ignore[attr-defined]
    return client


def test_list_get_and_filters(api: TestClient, make_aoi: MakeAoi, add_job: AddJob, assets: Any) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi()
    job = add_job(a1, "succeeded")
    id1, _ = assets.add(a1, job)
    id2, _ = assets.add(a2)
    body = api.get("/api/v1/assets").json()
    assert body["total"] == 2 and {i["id"] for i in body["items"]} == {str(id1), str(id2)}
    assert [i["id"] for i in api.get(f"/api/v1/assets?aoi_id={a1}").json()["items"]] == [str(id1)]
    assert [i["id"] for i in api.get(f"/api/v1/assets?job_id={job}").json()["items"]] == [str(id1)]
    assert api.get(f"/api/v1/assets?project_id={p}").json()["total"] == 1
    one = api.get(f"/api/v1/assets/{id1}").json()
    assert one["kind"] == "scene_catalog" and one["job_id"] == str(job) and one["provenance"] == {"t": 1}
    assert api.get(f"/api/v1/assets/{id2}").json()["job_id"] is None
    assert api.get("/api/v1/assets?limit=0").status_code == 422
    assert api.get("/api/v1/assets?limit=101").status_code == 422
    assert api.get(f"/api/v1/assets/{uuid.uuid4()}").json()["error"]["code"] == "asset_not_found"


def test_the_response_exposes_no_storage_key_and_no_scientific_fields(
    api: TestClient, make_aoi: MakeAoi, assets: Any
) -> None:
    _, a = make_aoi()
    aid, key = assets.add(a)
    text_ = api.get(f"/api/v1/assets/{aid}").text
    assert key not in text_ and "storage_key" not in text_ and "request_hash" not in text_
    spec = json.dumps(api.get("/openapi.json").json()["components"]["schemas"]["Asset"]).lower()
    assert not any(
        w in spec for w in ("confidence", "uncertainty", "probability", '"score', "interpretation")
    )


def test_content_download_headers_and_missing_file(
    api: TestClient, make_aoi: MakeAoi, assets: Any, storage: LocalStorage
) -> None:
    _, a = make_aoi()
    aid, key = assets.add(a)
    r = api.get(f"/api/v1/assets/{aid}/content")
    assert (
        r.status_code == 200
        and r.content == b"{}"
        and r.headers["content-type"].startswith("application/json")
    )
    assert (
        r.headers["x-content-type-options"] == "nosniff" and "attachment" in r.headers["content-disposition"]
    )
    assert r.headers["etag"] == '"' + "0" * 64 + '"'
    storage.delete(key)
    gone = api.get(f"/api/v1/assets/{aid}/content")
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "asset_file_missing"
    assert api.get(f"/api/v1/assets/{uuid.uuid4()}/content").json()["error"]["code"] == "asset_not_found"


def test_delete_returns_the_explicit_schema_and_removes_row_and_file(
    api: TestClient, engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, storage: LocalStorage
) -> None:
    _, a = make_aoi()
    aid, key = assets.add(a, add_job(a, "succeeded"))
    r = api.delete(f"/api/v1/assets/{aid}")
    assert r.status_code == 200 and r.json() == {"deleted": True, "files_pending_cleanup": 0}
    assert not storage.exists(key) and api.get(f"/api/v1/assets/{aid}").status_code == 404
    again = api.delete(f"/api/v1/assets/{aid}")
    assert again.status_code == 404 and again.json()["error"]["code"] == "asset_not_found"
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM storage_tombstone")).scalar_one() == 0


def test_delete_reports_pending_cleanup_without_failing_the_committed_deletion(
    api: TestClient, engine: Engine, make_aoi: MakeAoi, assets: Any, storage: LocalStorage
) -> None:
    """Simulated storage failure after the commit."""

    class Failing(LocalStorage):
        def delete(self, key: str) -> None:
            raise OSError("disk says no")

    _, a = make_aoi()
    aid, key = assets.add(a)
    api.app.state.storage = Failing(storage._root)  # type: ignore[attr-defined]
    r = api.delete(f"/api/v1/assets/{aid}")
    assert r.status_code == 200 and r.json() == {"deleted": True, "files_pending_cleanup": 1}
    assert storage.exists(key)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM data_asset")).scalar_one() == 0


def test_asset_of_a_running_job_cannot_be_deleted(
    api: TestClient, make_aoi: MakeAoi, add_job: AddJob, assets: Any
) -> None:
    _, a = make_aoi()
    aid, _ = assets.add(a, add_job(a, "running"))
    r = api.delete(f"/api/v1/assets/{aid}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "has_active_jobs"
    assert api.get(f"/api/v1/assets/{aid}").status_code == 200


def test_there_is_no_way_to_create_or_modify_assets_through_the_api(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]
    methods = {m for p, ops in paths.items() if p.startswith("/api/v1/assets") for m in ops}
    assert methods == {"get", "delete"}
    for verb in (api.post, api.put, api.patch):
        assert verb("/api/v1/assets", json={}).status_code in (404, 405)
        assert verb(f"/api/v1/assets/{uuid.uuid4()}", json={}).status_code in (404, 405)
