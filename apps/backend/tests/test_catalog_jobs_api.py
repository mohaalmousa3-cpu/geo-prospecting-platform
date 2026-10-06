"""T3 — public creation of fixtures-only `catalog_search` jobs (Phase 3a, CP4).

Labels: *real* = real HTTP app + real PostgreSQL; *simulated* = a stub queue raising a queue error.
Nothing here starts a worker: execution is covered end to end in tests/integration/test_catalog_search_flow.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.main import create_app
from geo_common.config import Settings
from geo_common.queue import JobQueue, JobRecord, QueueBusyError
from geo_common.queue_pg import PostgresJobQueue

pytestmark = pytest.mark.integration
BODY = {"start": "2026-01-01", "end": "2026-06-30", "collections": ["synthetic-optical"]}
RECT = {"method": "rectangle", "name": "r", "west": 10.02, "south": 40.02, "east": 10.05, "north": 40.05}
Api = Callable[..., TestClient]


@pytest.fixture
def api(engine: Engine) -> Iterator[Api]:
    """Factory: an app whose `CONNECTOR_MODE` (and other settings) are chosen per test."""
    opened: list[Any] = []

    def make(mode: str = "fixture", queue: JobQueue | None = None, **kw: Any) -> TestClient:
        s = Settings(  # type: ignore[call-arg]
            _env_file=None, CONNECTOR_MODE=mode, CORS_ALLOWED_ORIGINS="http://localhost:3000", **kw
        )
        cm = TestClient(create_app(s, engine=engine, queue=queue))
        opened.append(cm)
        return cm.__enter__()

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def project_and_aoi(c: TestClient, name: str = "p") -> tuple[str, str]:
    p = c.post("/api/v1/projects", json={"name": name}).json()["id"]
    r = c.post("/api/v1/aois", json={**RECT, "project_id": p})
    assert r.status_code == 201, r.text
    return p, r.json()["id"]


def job_count(engine: Engine) -> int:
    with engine.connect() as c:
        return int(c.execute(text("SELECT count(*) FROM job")).scalar_one())


def post(c: TestClient, aoi: Any, payload: Any = None, **extra: Any) -> Any:
    body: dict[str, Any] = {"type": "catalog_search", "payload": BODY if payload is None else payload}
    if aoi is not None:
        body["aoi_id"] = aoi
    return c.post("/api/v1/jobs", json={**body, **extra})


# ------------------------------------------------------------------ fixture mode: the happy path (real)
def test_fixture_mode_queues_a_job_bound_to_the_aoi_with_the_project_derived_from_it(
    api: Api, engine: Engine
) -> None:
    c = api("fixture")
    p, a = project_and_aoi(c)
    r = post(c, a, {"collections": ["b", "a", "a"], "start": "2026-01-01", "end": "2026-01-31"})
    assert r.status_code == 201, r.text
    job = r.json()
    assert (job["type"], job["status"], job["aoi_id"], job["project_id"]) == (
        "catalog_search",
        "queued",
        a,
        p,
    )
    assert c.get(f"/api/v1/jobs/{job['id']}").json()["project_id"] == p
    with engine.connect() as conn:  # the stored row: project from the AOI, payload normalised and explicit
        row = conn.execute(
            text("SELECT j.project_id, j.aoi_id, j.payload, a.project_id AS ap FROM job j JOIN aoi a "
                 "ON a.id = j.aoi_id WHERE j.id = :i"), {"i": job["id"]}
        ).one()  # fmt: skip
    assert str(row.project_id) == str(row.ap) == p and str(row.aoi_id) == a
    assert row.payload == {
        "start": "2026-01-01",
        "end": "2026-01-31",
        "collections": ["a", "b"],  # sorted and de-duplicated
        "max_items": 20,  # the default is made explicit (MAX_SCENES_PER_JOB), never filled in silently
    }


def test_noop_jobs_are_unchanged_and_report_null_targets(api: Api) -> None:
    c = api("disabled")  # noop does not depend on CONNECTOR_MODE
    r = c.post("/api/v1/jobs", json={"type": "noop"})
    assert r.status_code == 201
    assert r.json()["aoi_id"] is None and r.json()["project_id"] is None


# ------------------------------------------------------------------ CONNECTOR_MODE (real)
def test_disabled_mode_is_explicit_stable_and_creates_nothing(api: Api, engine: Engine) -> None:
    c = api("disabled")  # also the default of Settings
    _, a = project_and_aoi(c)
    for _ in range(2):  # stable: the same answer every time
        r = post(c, a)
        assert r.status_code == 409 and r.json()["error"]["code"] == "connectors_disabled", r.text
        assert "CONNECTOR_MODE=disabled" in r.json()["error"]["message"]
    assert job_count(engine) == 0
    assert Settings(_env_file=None).CONNECTOR_MODE == "disabled"  # type: ignore[call-arg]


def test_live_mode_is_explicitly_not_available_and_stable(api: Api, engine: Engine) -> None:
    c = api("live")
    _, a = project_and_aoi(c)
    for _ in range(2):
        r = post(c, a)
        assert r.status_code == 501 and r.json()["error"]["code"] == "connector_live_not_available", r.text
        assert "fixtures only" in r.json()["error"]["message"]
    assert job_count(engine) == 0


@pytest.mark.parametrize("mode", ["disabled", "live"])
def test_refusal_precedence_validation_then_mode_then_target(api: Api, engine: Engine, mode: str) -> None:
    c = api(mode)
    _, a = project_and_aoi(c)
    missing = uuid.uuid4()
    assert post(c, a, {"start": "nope"}).status_code == 422  # shape first, even when the mode refuses
    assert post(c, None).status_code == 422
    assert post(c, str(missing)).status_code in (409, 501)  # mode before the AOI lookup: no AOI query leaks
    assert job_count(engine) == 0


def test_the_request_cannot_select_a_dataset_provider_host_or_cache(api: Api, engine: Engine) -> None:
    c = api("fixture")
    _, a = project_and_aoi(c)
    for key in ("fixture", "provider", "connector", "dataset", "url", "host", "port", "cache", "dem",
                "user_vector", "project_id", "token", "http_client"):  # fmt: skip
        r = post(c, a, {**BODY, key: "x"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", key
        assert key in r.json()["error"]["message"], key
    assert job_count(engine) == 0


# ------------------------------------------------------------------ targeting (real)
def test_a_missing_or_malformed_aoi_is_rejected_and_an_unknown_one_is_404(api: Api, engine: Engine) -> None:
    c = api("fixture")
    p, a = project_and_aoi(c)
    r = post(c, None)
    assert r.status_code == 422 and "aoi_id is required" in r.json()["error"]["message"]
    for bad in (None, "", "not-a-uuid", 5, [str(a)], {"id": a}):  # None => the key is sent as null
        body = {"type": "catalog_search", "payload": BODY, "aoi_id": bad}
        assert c.post("/api/v1/jobs", json=body).status_code == 422, bad
    r = post(c, str(uuid.uuid4()))
    assert r.status_code == 404 and r.json()["error"]["code"] == "aoi_not_found"
    assert job_count(engine) == 0
    assert c.post("/api/v1/jobs", json={"type": "noop", "aoi_id": a}).status_code == 422  # noop takes none
    assert p


def test_a_client_cannot_choose_the_project_in_any_position(api: Api, engine: Engine) -> None:
    c = api("fixture")
    p1, a1 = project_and_aoi(c, "one")
    p2, _ = project_and_aoi(c, "two")
    for pid in (p2, p1, str(uuid.uuid4()), None, "x"):  # conflicting, matching, unknown, null, malformed
        r = post(c, a1, project_id=pid)  # top level: not a field of the request
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", pid
        assert "project_id" in json.dumps(r.json()), pid
        r = post(c, a1, {**BODY, "project_id": pid})  # inside the payload
        assert r.status_code == 422 and "project_id" in r.json()["error"]["message"], pid
    assert job_count(engine) == 0
    ok = post(c, a1)  # the only way to get a project is through the AOI
    assert ok.status_code == 201 and ok.json()["project_id"] == p1


# ------------------------------------------------------------------ payload shape and limits (real)
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"start": "2026-01-01"},
        {"start": "2026-01-01", "end": "2026-02-01"},  # no collections
        {**BODY, "start": "2026-1-1"},
        {**BODY, "start": "20260101"},
        {**BODY, "start": "2026-02-30"},
        {**BODY, "start": 20260101},
        {**BODY, "start": None},
        {**BODY, "end": "2025-12-31"},  # precedes start
        {**BODY, "end": "2027-06-30"},  # window above MAX_TIME_WINDOW_DAYS (365)
        {**BODY, "collections": []},
        {**BODY, "collections": "synthetic-optical"},
        {**BODY, "collections": [5]},
        {**BODY, "collections": ["../x"]},
        {**BODY, "collections": ["a b"]},
        {**BODY, "collections": [""]},
        {**BODY, "collections": ["c" * 65]},
        {**BODY, "collections": [f"c{i}" for i in range(11)]},  # more than MAX_COLLECTIONS (10)
        {**BODY, "max_items": 0},
        {**BODY, "max_items": -1},
        {**BODY, "max_items": True},
        {**BODY, "max_items": "5"},
        {**BODY, "max_items": 1.5},
        {**BODY, "max_items": 21},  # above MAX_SCENES_PER_JOB (20): rejected, never clamped
    ],
)
def test_invalid_payloads_are_rejected_without_creating_a_job(api: Api, engine: Engine, payload: Any) -> None:
    c = api("fixture")
    _, a = project_and_aoi(c)
    r = post(c, a, payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", r.text
    assert job_count(engine) == 0


def test_boundary_values_are_accepted_exactly_at_the_limits(api: Api, engine: Engine) -> None:
    c = api("fixture")
    _, a = project_and_aoi(c)
    edge = {
        "start": "2026-01-01",
        "end": "2026-12-31",  # 365 days = MAX_TIME_WINDOW_DAYS
        "collections": [f"c{i}" for i in range(10)],  # = MAX_COLLECTIONS
        "max_items": 20,  # = MAX_SCENES_PER_JOB
    }
    assert post(c, a, edge).status_code == 201
    assert post(c, a, {**edge, "start": "2025-12-31"}).status_code == 422  # 366 days
    assert job_count(engine) == 1


def test_limits_follow_the_server_settings_not_the_client(api: Api, engine: Engine) -> None:
    c = api("fixture", MAX_TIME_WINDOW_DAYS=10, MAX_SCENES_PER_JOB=3)
    _, a = project_and_aoi(c)
    assert post(c, a, {**BODY, "end": "2026-01-10"}).status_code == 201
    assert post(c, a, {**BODY, "end": "2026-01-11"}).status_code == 422
    assert post(c, a, {**BODY, "end": "2026-01-10", "max_items": 4}).status_code == 422
    r = post(c, a, {**BODY, "end": "2026-01-10"})
    assert r.status_code == 201 and job_count(engine) == 2


def test_payloads_accepted_by_the_api_are_accepted_by_the_worker_side_checks() -> None:
    """Parity (pure functions): the API is at least as strict as the handler's own re-validation."""
    from datetime import date

    from app.catalog_jobs import validate_catalog_payload
    from geo_connectors.contracts import FetchContext
    from geo_connectors.handler import _parse_payload

    s = Settings(_env_file=None, CONNECTOR_MODE="fixture")  # type: ignore[call-arg]
    aoi = {"type": "Polygon", "coordinates": [[[10.0, 40.0], [10.1, 40.0], [10.1, 40.1], [10.0, 40.0]]]}
    cases = [
        BODY,
        {**BODY, "max_items": 1},
        {**BODY, "max_items": 20, "collections": ["z", "a", "a"]},
        {"start": "2026-01-01", "end": "2026-12-31", "collections": ["x"]},
        {"start": "2026-02-28", "end": "2026-02-28", "collections": ["x"]},
    ]
    for raw in cases:
        stored = validate_catalog_payload(raw, s)
        p = _parse_payload(stored, s)
        FetchContext(
            aoi_geojson=aoi,
            start=p["start"],
            end=p["end"],
            collections=p["collections"],
            max_items=p["max_items"],
            max_window_days=s.MAX_TIME_WINDOW_DAYS,
        ).validate()  # must not raise
        assert p["start"] == date.fromisoformat(stored["start"]) and p["max_items"] == stored["max_items"]
        assert p["fixture_name"] == "synthetic_catalog_v1"  # the default; the API cannot select another


# ------------------------------------------------------------------ queue behaviour is unchanged
def test_the_queue_limit_applies_to_catalog_search_jobs(api: Api, engine: Engine) -> None:
    c = api("fixture", MAX_QUEUED_JOBS=2)
    _, a = project_and_aoi(c)
    assert post(c, a).status_code == 201 and post(c, a).status_code == 201
    r = post(c, a)
    assert r.status_code == 429 and r.json()["error"]["code"] == "queue_full"
    assert c.post("/api/v1/jobs", json={"type": "noop"}).status_code == 429  # one shared limit
    assert job_count(engine) == 2


class _BusyQueue(PostgresJobQueue):
    def enqueue(self, *a: Any, **kw: Any) -> JobRecord:
        raise QueueBusyError("simulated lock contention")


def test_a_busy_queue_gives_503_retry_later_for_catalog_search_too(api: Api, engine: Engine) -> None:
    """Simulated (stub queue): the real exhaustion of the budget is exercised in test_jobs_busy_api.py."""
    c = api("fixture", queue=_BusyQueue(engine, max_queued_jobs=10, default_max_attempts=2))
    _, a = project_and_aoi(c)
    r = post(c, a)
    assert r.status_code == 503 and r.json()["error"]["code"] == "retry_later"
    assert job_count(engine) == 0


def test_only_noop_and_catalog_search_exist_as_job_types(api: Api) -> None:
    c = api("fixture")
    for t in ("dem_fetch", "user_vector", "thermal", "gold_prospectivity", "earth_engine"):
        assert c.post("/api/v1/jobs", json={"type": t, "payload": {}}).status_code == 422, t


def test_a_catalog_search_job_can_be_cancelled_before_it_runs(api: Api, engine: Engine) -> None:
    c = api("fixture")
    _, a = project_and_aoi(c)
    jid = post(c, a).json()["id"]
    r = c.post(f"/api/v1/jobs/{jid}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["aoi_id"] == a
