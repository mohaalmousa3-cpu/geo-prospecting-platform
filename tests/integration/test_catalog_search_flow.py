"""T3/T4 end to end — API → queue → the real runner (spawn child) → registered handler → assets → API (CP4).

Labels: *real* = real HTTP app, PostgreSQL, filesystem storage and the runner's real spawn child process;
*real crash* = a real `os._exit` of the handler process after publication; *audit* = a `sys.addaudithook`
record of socket events inside the child (it is not an egress firewall); *simulated* = none in this file.
Everything is offline: CONNECTOR_MODE=fixture reads committed synthetic fixtures.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from app.main import create_app
from geo_common.assets_pg import reconcile_report
from geo_common.config import Settings
from geo_common.queue import JobQueue
from geo_common.storage import LocalStorage
from runner.handlers import DEFAULT_HANDLERS
from runner.loop import Runner

pytestmark = [pytest.mark.integration, pytest.mark.timeout(180)]
REPO = Path(__file__).resolve().parents[2]
TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")
RECT = {"method": "rectangle", "name": "r", "west": 10.02, "south": 40.02, "east": 10.05, "north": 40.05}
BODY = {"start": "2026-01-01", "end": "2026-12-31", "collections": ["synthetic-optical"]}
FIXTURES = REPO / "workers/connectors/src/geo_connectors/fixtures"


@dataclass
class Stack:
    client: TestClient
    queue: JobQueue
    root: Path
    engine: Engine
    monkeypatch: pytest.MonkeyPatch

    def storage(self) -> LocalStorage:
        return LocalStorage(self.root)

    def runner(self, handlers: dict[str, str] | None = None) -> Runner:
        return Runner(
            self.queue,
            worker_id="cp4-worker",
            lease_seconds=30,
            poll_interval=0.05,
            job_timeout=90,
            handlers=handlers or DEFAULT_HANDLERS,
        )

    def work(self, handlers: dict[str, str] | None = None) -> None:
        assert self.runner(handlers).run_once(), "the worker found no job to process"

    def project_and_aoi(self, rect: dict[str, Any] | None = None) -> tuple[str, str]:
        p = self.client.post("/api/v1/projects", json={"name": "p"}).json()["id"]
        r = self.client.post("/api/v1/aois", json={**(rect or RECT), "project_id": p})
        assert r.status_code == 201, r.text
        return p, r.json()["id"]

    def job(self, aoi: str, payload: dict[str, Any] | None = None) -> str:
        r = self.client.post(
            "/api/v1/jobs", json={"type": "catalog_search", "aoi_id": aoi, "payload": payload or BODY}
        )
        assert r.status_code == 201, r.text
        return str(r.json()["id"])

    def get(self, job_id: str) -> dict[str, Any]:
        return dict(self.client.get(f"/api/v1/jobs/{job_id}").json())

    def count(self, table: str) -> int:
        with self.engine.connect() as c:
            return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608

    def files(self) -> list[str]:
        st = self.storage()
        return list(st.iter_keys()) + [f".staging/{n}" for n, _m, _s in st.iter_staging()]


def db_env() -> dict[str, str]:
    u = make_url(TEST_URL)
    return {
        "POSTGRES_HOST": str(u.host),
        "POSTGRES_PORT": str(u.port or 5432),
        "POSTGRES_USER": str(u.username),
        "POSTGRES_PASSWORD": str(u.password),
        "POSTGRES_DB": str(u.database),
    }


@pytest.fixture
def stack(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Stack]:
    root = tmp_path / "storage"
    for k, v in {**db_env(), "CONNECTOR_MODE": "fixture", "STORAGE_LOCAL_PATH": str(root)}.items():
        monkeypatch.setenv(k, v)  # inherited by the runner's spawn child
    s = Settings(  # type: ignore[call-arg]
        _env_file=None,
        CONNECTOR_MODE="fixture",
        STORAGE_LOCAL_PATH=str(root),
        CORS_ALLOWED_ORIGINS="http://localhost:3000",
    )
    with TestClient(create_app(s, engine=engine)) as client:
        yield Stack(client, client.app.state.queue, root, engine, monkeypatch)  # type: ignore[attr-defined]


def expected_ids(
    aoi_bbox: tuple[float, float, float, float], collections: set[str], lo: str, hi: str
) -> list[str]:
    """Independent re-computation of what the synthetic fixture should return for a request."""
    doc = json.loads((FIXTURES / "synthetic_catalog_v1.json").read_text())
    hits = []
    for it in doc["items"]:
        w, s, e, n = it["bbox"]
        day = date.fromisoformat(it["datetime"][:10])
        overlaps = w <= aoi_bbox[2] and aoi_bbox[0] <= e and s <= aoi_bbox[3] and aoi_bbox[1] <= n
        if (
            it["collection"] in collections
            and date.fromisoformat(lo) <= day <= date.fromisoformat(hi)
            and overlaps
        ):
            hits.append((it["datetime"], it["id"]))
    return [i for _, i in sorted(hits)]


# ------------------------------------------------------------------ T4: non-empty fixture run (real)
def test_a_job_created_through_the_api_publishes_the_expected_fixture_asset_and_provenance(
    stack: Stack,
) -> None:
    p, a = stack.project_and_aoi()
    jid = stack.job(a)
    stack.work()
    job = stack.get(jid)
    assert job["status"] == "succeeded" and job["attempts"] == 1, job
    assert (job["aoi_id"], job["project_id"]) == (a, p)

    listing = stack.client.get(f"/api/v1/assets?job_id={jid}").json()
    assert listing["total"] == 1
    asset = listing["items"][0]
    assert (asset["kind"], asset["project_id"], asset["aoi_id"], asset["job_id"]) == (
        "scene_catalog",
        p,
        a,
        jid,
    )
    content = stack.client.get(f"/api/v1/assets/{asset['id']}/content")
    assert content.status_code == 200 and content.headers["x-content-type-options"] == "nosniff"
    data = content.content
    assert hashlib.sha256(data).hexdigest() == asset["sha256"] and len(data) == asset["size_bytes"]
    assert content.headers["etag"].strip('"') == asset["sha256"]

    doc = json.loads(data)
    want = expected_ids((10.02, 40.02, 10.05, 40.05), {"synthetic-optical"}, "2026-01-01", "2026-12-31")
    assert want, "the fixture must cover this request, otherwise the test proves nothing"
    assert [r["item_id"] for r in doc["records"]] == want
    assert doc["source"]["synthetic"] is True and doc["source"]["kind"] == "fixture"
    flat = json.dumps(doc).lower()
    assert not any(w in flat for w in ("confidence", "uncertainty", "probability", '"score"', "prospectiv"))

    prov = stack.client.get(f"/api/v1/assets/{asset['id']}").json()["provenance"]  # CLAUDE.md §4.6 fields
    assert {"dataset", "dataset_version", "retrieved_at", "parameters", "code_version", "synthetic"} <= set(
        prov["source"]
    )
    assert prov["job_id"] == jid and prov["asset_id"] == asset["id"] and prov["kind"] == "scene_catalog"
    with stack.engine.connect() as c:
        rh = c.execute(text("SELECT request_hash, storage_key FROM data_asset")).one()
    assert rh.request_hash == prov["request_hash"] and rh.request_hash.startswith("v1:")
    assert rh.storage_key == f"projects/{p}/aois/{a}/jobs/{jid}/{asset['id']}.json"
    assert stack.files() == [rh.storage_key]
    assert (stack.count("result"), stack.count("provenance"), stack.count("data_asset")) == (0, 1, 1)


# ------------------------------------------------------------------ T4: zero results (real)
@pytest.mark.parametrize(
    ("what", "rect", "payload"),
    [
        ("window with no items", None, {**BODY, "start": "2020-01-01", "end": "2020-01-31"}),
        ("collection with no items", None, {**BODY, "collections": ["synthetic-unlisted"]}),
        (
            "AOI away from every footprint",
            {**RECT, "west": 0.0, "south": 0.0, "east": 0.03, "north": 0.03},
            None,
        ),
    ],
)
def test_zero_results_end_in_insufficient_data_and_create_no_result_envelope_or_asset(
    stack: Stack, what: str, rect: dict[str, Any] | None, payload: dict[str, Any] | None
) -> None:
    _, a = stack.project_and_aoi(rect)
    jid = stack.job(a, payload)
    stack.work()
    job = stack.get(jid)
    assert job["status"] == "insufficient_data", (what, job)
    assert (
        job["error"] == "no catalogue items matched the request"
    )  # the explanation, not a scientific result
    assert (stack.count("result"), stack.count("data_asset"), stack.count("provenance")) == (0, 0, 0)
    assert stack.files() == []
    assert stack.client.get(f"/api/v1/assets?job_id={jid}").json()["total"] == 0
    assert not any(k in job for k in ("confidence", "uncertainty", "score", "envelope", "result"))


# ------------------------------------------------------------------ T4: idempotency (real crash + retry)
def test_a_worker_death_after_publication_is_retried_without_a_duplicate_asset(
    stack: Stack, tmp_path: Path
) -> None:
    """The handler process really dies (`os._exit(137)`) after the asset is committed; the runner requeues the
    job; attempt 2 finds the existing asset under request_hash and succeeds without a second row or file."""
    stack.monkeypatch.setenv("CP4_MARKER", str(tmp_path / "died"))
    _, a = stack.project_and_aoi()
    jid = stack.job(a)
    handlers = {"catalog_search": "cp4_handlers:publish_then_die"}
    stack.work(handlers)
    mid = stack.get(jid)
    assert mid["status"] == "queued" and mid["attempts"] == 1 and "exit code 137" in mid["error"], mid
    assert stack.count("data_asset") == 1  # already committed before the death
    first_key = stack.files()
    stack.work(handlers)
    done = stack.get(jid)
    assert done["status"] == "succeeded" and done["attempts"] == 2, done
    assert "already published" in done["error"]
    assert stack.count("data_asset") == 1 and stack.count("provenance") == 1
    assert stack.files() == first_key  # the retry's duplicate file was removed; the staging area is empty


def test_the_same_request_in_two_jobs_makes_two_assets_idempotency_is_per_job(stack: Stack) -> None:
    _, a = stack.project_and_aoi()
    j1, j2 = stack.job(a), stack.job(a)
    stack.work()
    stack.work()
    with stack.engine.connect() as c:
        rows = c.execute(text("SELECT job_id, request_hash FROM data_asset ORDER BY created_at")).all()
    assert len(rows) == 2 and rows[0].request_hash == rows[1].request_hash  # same request, same hash
    assert {str(r.job_id) for r in rows} == {j1, j2}  # not result deduplication across jobs
    assert len(stack.files()) == 2


# ------------------------------------------------------------------ CONNECTOR_MODE seen by the worker (real)
@pytest.mark.parametrize(("mode", "needle"), [("disabled", "connectors disabled"), ("live", "not available")])
def test_a_worker_whose_mode_is_not_fixture_fails_the_job_explicitly_and_writes_nothing(
    stack: Stack, mode: str, needle: str
) -> None:
    _, a = stack.project_and_aoi()
    jid = stack.job(a)  # the API was in fixture mode; the worker's configuration differs
    stack.monkeypatch.setenv("CONNECTOR_MODE", mode)
    stack.work()
    job = stack.get(jid)
    assert job["status"] == "failed" and needle in job["error"], job
    assert (stack.count("data_asset"), stack.count("provenance"), stack.count("result")) == (0, 0, 0)
    assert stack.files() == []


# ------------------------------------------------------------------ lifecycle after publication (real)
def test_deleting_the_aoi_removes_the_asset_and_its_file_and_reconcile_stays_report_only(
    stack: Stack, tmp_path: Path
) -> None:
    p, a = stack.project_and_aoi()
    jid = stack.job(a)
    stack.work()
    assert stack.get(jid)["status"] == "succeeded"
    r = stack.client.delete(f"/api/v1/aois/{a}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "needs_cascade"  # assets need the flag
    assert stack.count("data_asset") == 1 and len(stack.files()) == 1

    # `make reconcile-assets` (the same command line, run as a subprocess): report only
    stray = stack.root / "stray" / "unreferenced.json"
    stray.parent.mkdir(parents=True)
    stray.write_text("{}")
    before = sorted(stack.files())
    run = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/reconcile_assets.py"],
        env={**os.environ, **db_env(), "STORAGE_LOCAL_PATH": str(stack.root)},
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert (
        "unreferenced files (report only, nothing deleted): 1" in run.stdout
        and "stray/unreferenced.json" in run.stdout
    )
    assert stray.exists() and sorted(stack.files()) == before and stack.count("data_asset") == 1

    r = stack.client.delete(f"/api/v1/aois/{a}?delete_dependents=true")
    assert r.status_code == 204
    assert (stack.count("data_asset"), stack.count("provenance"), stack.count("job")) == (0, 0, 0)
    assert stack.files() == [
        "stray/unreferenced.json"
    ]  # the asset file is gone; the stray one is only reported
    assert reconcile_report(stack.engine, stack.storage()).unreferenced_files == ["stray/unreferenced.json"]
    assert p


# ------------------------------------------------------------------ no network in the worker path (audit)
def test_the_runner_child_connects_only_to_the_test_database_and_never_inside_the_fetch_window(
    stack: Stack, tmp_path: Path
) -> None:
    """Audit, not a firewall: a `sys.addaudithook` inside the runner's child records every socket event while
    the real handler runs a real API-created job. Allowed destination: the test PostgreSQL endpoint only."""
    out = tmp_path / "audit.json"
    stack.monkeypatch.setenv("CP4_AUDIT_OUT", str(out))
    _, a = stack.project_and_aoi()
    jid = stack.job(a)
    stack.work({"catalog_search": "cp4_handlers:audited_catalog_search"})
    assert stack.get(jid)["status"] == "succeeded"
    events = json.loads(out.read_text())
    assert events, "the database connections must have been observed"
    url = make_url(TEST_URL)
    host, port = str(url.host), int(url.port or 5432)
    allowed = {ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    for e in events:
        assert not e["in_fetch_window"], e
        if e["event"] == "socket.connect":
            addr = ast.literal_eval(e["args"][0])
            assert addr[0] in allowed and addr[1] == port, e
        else:
            assert e["args"][0] == host, e
