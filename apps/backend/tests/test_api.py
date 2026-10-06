from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.main import create_app
from geo_common.config import Settings

pytestmark = pytest.mark.integration
SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi.json"


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["x-request-id"]


def test_ready_ok(client: TestClient) -> None:
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_ready_fails_when_db_down(settings: Settings) -> None:
    dead = create_engine("postgresql+pg8000://x:y@127.0.0.1:1/none", connect_args={"timeout": 1})
    with TestClient(create_app(settings, engine=dead)) as c:
        r = c.get("/api/v1/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "unavailable"
    assert "127.0.0.1" not in r.text  # no connection details leak


def test_request_id_echo_and_sanitising(client: TestClient) -> None:
    assert (
        client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    )
    bad = client.get("/api/v1/health", headers={"X-Request-ID": "x" * 200}).headers["x-request-id"]
    assert len(bad) == 32


def test_cors_allow_list(client: TestClient) -> None:
    ok = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
    pre = client.options(
        "/api/v1/jobs",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in pre.headers


def test_oversize_body_rejected(client: TestClient, settings: Settings) -> None:
    big = b"{" + b" " * (settings.max_request_bytes + 10) + b"}"
    r = client.post("/api/v1/jobs", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_noop_job_lifecycle_and_cancel(client: TestClient) -> None:
    r = client.post("/api/v1/jobs", json={"type": "noop"})
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "queued" and job["type"] == "noop" and job["attempts"] == 0
    got = client.get(f"/api/v1/jobs/{job['id']}")
    assert got.status_code == 200 and got.json()["id"] == job["id"]
    c = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert c.status_code == 200 and c.json()["status"] == "cancelled"


@pytest.mark.parametrize(
    "body",
    [
        {"type": "thermal"},
        {"type": "gold_prospectivity"},
        {},
        {"type": "noop", "payload": {"sleep_seconds": 9999}},
        {"type": "noop", "payload": {"aoi": {"type": "Polygon"}}},
        {"type": "noop", "aoi_id": "x"},
    ],
)
def test_invalid_job_requests_422(client: TestClient, body: dict[str, object]) -> None:
    r = client.post("/api/v1/jobs", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_queue_full_names_limit(client: TestClient) -> None:
    for _ in range(3):
        assert client.post("/api/v1/jobs", json={"type": "noop"}).status_code == 201
    r = client.post("/api/v1/jobs", json={"type": "noop"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "queue_full" and "MAX_QUEUED_JOBS=3" in r.json()["error"]["message"]


def test_unknown_and_malformed_ids(client: TestClient) -> None:
    assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    assert client.post(f"/api/v1/jobs/{uuid4()}/cancel").status_code == 404
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422


def test_only_expected_routes_exist_and_no_result_routes(client: TestClient) -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/cancel",
        "/api/v1/aois",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
        "/api/v1/aois/limits",
        "/api/v1/aois/preview",
        "/api/v1/aois/upload",
        "/api/v1/aois/{aoi_id}",
        "/api/v1/assets",  # Phase 3a CP3: read/delete only, no creation route (owner-authorised)
        "/api/v1/assets/{asset_id}",
        "/api/v1/assets/{asset_id}/content",
        "/api/v1/aois/{aoi_id}/assets",  # Phase 3a closure: read-only, AOI-scoped
        "/api/v1/connectors",  # Phase 3a closure: read-only capability description
    }


def test_openapi_snapshot(client: TestClient) -> None:
    current = client.get("/openapi.json").json()
    if os.environ.get("UPDATE_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    assert current == json.loads(SNAPSHOT.read_text()), "OpenAPI changed; rerun with UPDATE_SNAPSHOT=1"
