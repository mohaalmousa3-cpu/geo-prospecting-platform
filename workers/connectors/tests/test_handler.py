"""catalog_search handler: publication protocol, cancellation boundaries, cleanup, crash boundary.

Labels: *real* = real database/file behaviour; *simulated* = injected storage failure or a state change made at a
test seam (not evidence of concurrency); *crash* = a real process kill at a chosen boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from db_concurrency import Held
from db_helpers import (
    PAYLOAD,
    TEST_URL,
    W,
    context,
    count,
    db_env,
    fixture_aoi,
    running_job,
    settings_for,
)
from sqlalchemy import Engine, text

from geo_common.assets_pg import cleanup_own_files, get_asset, reconcile_report
from geo_common.storage import LocalStorage
from geo_connectors.errors import (
    ConnectorRequestError,
    ConnectorsDisabled,
    LiveModeNotAvailable,
    PublicationBusyError,
    PublicationRefusedError,
)
from geo_connectors.handler import run_catalog_search

pytestmark = pytest.mark.integration
REPO = Path(__file__).resolve().parents[3]


def run(
    engine: Engine, storage: LocalStorage, job: object, tmp: Path, payload: dict | None = None, **kw: object
):  # type: ignore[no-untyped-def]
    return run_catalog_search(
        PAYLOAD if payload is None else payload,
        context(job),  # type: ignore[arg-type]
        engine=engine,
        storage=storage,
        settings=kw.pop("settings", settings_for(tmp)),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def files(storage: LocalStorage) -> list[str]:
    return list(storage.iter_keys()) + [f".staging/{n}" for n, _m, _s in storage.iter_staging()]


# ------------------------------------------------------------------ success, idempotency, empty (real)
def test_publishes_one_asset_with_file_provenance_and_metadata_only(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    p, a = fixture_aoi(engine)
    job = running_job(engine, a)
    out = run(engine, storage, job, tmp_path)
    assert out.status == "succeeded" and "published asset" in out.message
    items = [x for x in files(storage)]
    assert len(items) == 1 and items[0].startswith(f"projects/{p}/aois/{a}/jobs/{job}/")
    with engine.connect() as c:
        row = c.execute(
            text("SELECT id, sha256, size_bytes, request_hash, kind, media_type FROM data_asset")
        ).one()
    data = storage.get(items[0])
    assert hashlib.sha256(data).hexdigest() == row.sha256 and len(data) == row.size_bytes
    assert (
        row.kind == "scene_catalog"
        and row.media_type == "application/json"
        and row.request_hash.startswith("v1:")
    )
    doc = json.loads(data)
    assert doc["source"]["synthetic"] is True and doc["records"] and doc["asset_format"] == 1
    asset = get_asset(engine, row.id)
    assert asset is not None
    assert {"dataset", "dataset_version", "retrieved_at", "parameters", "code_version"} <= set(
        asset.provenance["source"]
    )
    flat = json.dumps(doc).lower()
    assert not any(w in flat for w in ("confidence", "uncertainty", "probability", '"score"'))


def test_a_rerun_for_the_same_job_is_an_idempotent_success_without_a_duplicate(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    first = run(engine, storage, job, tmp_path)
    second = run(engine, storage, job, tmp_path)  # e.g. attempt 2 after a lost lease
    assert "already published" in second.message and first.status == second.status == "succeeded"
    assert (count(engine, "data_asset"), len(files(storage))) == (1, 1)  # the duplicate file was removed


def test_zero_results_is_insufficient_data_with_no_asset_and_no_file(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    out = run(engine, storage, job, tmp_path, {**PAYLOAD, "fixture": "synthetic_catalog_empty_v1"})
    assert out.status == "insufficient_data" and "no catalogue items matched" in out.message
    assert (count(engine, "data_asset"), count(engine, "provenance"), count(engine, "result")) == (0, 0, 0)
    assert files(storage) == []


# ------------------------------------------------------------------ modes and payload
def test_disabled_and_live_modes_are_explicit_and_write_nothing(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    with pytest.raises(ConnectorsDisabled):
        run(engine, storage, job, tmp_path, settings=settings_for(tmp_path, "disabled"))
    with pytest.raises(LiveModeNotAvailable):
        run(engine, storage, job, tmp_path, settings=settings_for(tmp_path, "live"))
    assert count(engine, "data_asset") == 0 and files(storage) == []


@pytest.mark.parametrize(
    "payload",
    [{}, {**PAYLOAD, "start": "nope"}, {**PAYLOAD, "collections": 5}, {**PAYLOAD, "max_items": "x"},
     {**PAYLOAD, "end": "2030-01-01"}],
)  # fmt: skip
def test_invalid_payloads_are_rejected_before_any_write(
    engine: Engine, storage: LocalStorage, tmp_path: Path, payload: dict
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    with pytest.raises(ConnectorRequestError):
        run(engine, storage, job, tmp_path, payload)
    assert count(engine, "data_asset") == 0 and files(storage) == []


# ------------------------------------------------------------------ cancellation and refusal boundaries
class SpyStorage(LocalStorage):
    """Counts `put` calls: proves that nothing was even attempted, not merely cleaned up afterwards."""

    puts = 0

    def put(self, key: str, data: bytes) -> None:
        type(self).puts += 1
        super().put(key, data)


def test_cancellation_before_publication_writes_nothing(engine: Engine, tmp_path: Path) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    with engine.begin() as c:
        c.execute(text("UPDATE job SET cancel_requested = true WHERE id = :j"), {"j": job})
    st = SpyStorage(tmp_path / "s")
    SpyStorage.puts = 0
    out = run(engine, st, job, tmp_path)
    assert out.status == "cancelled" and "before publication" in out.message
    assert SpyStorage.puts == 0  # no file was ever written (not merely removed afterwards)
    assert count(engine, "data_asset") == 0 and files(st) == []


class CancelAfterPut(LocalStorage):
    """Simulated race at a seam: the cancellation is recorded after the file is written, before publication."""

    def __init__(self, root: Path, engine: Engine, job_holder: list[object]) -> None:
        super().__init__(root)
        self._engine, self._job = engine, job_holder

    def put(self, key: str, data: bytes) -> None:
        super().put(key, data)
        with self._engine.begin() as c:
            c.execute(text("UPDATE job SET cancel_requested = true WHERE id = :j"), {"j": self._job[0]})


def test_cancellation_between_file_write_and_publication_is_refused_and_cleaned(
    engine: Engine, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    st = CancelAfterPut(tmp_path / "s", engine, [job])
    out = run(engine, st, job, tmp_path)
    assert out.status == "cancelled"
    assert (
        count(engine, "data_asset") == 0 and files(st) == []
    )  # the worker's own key and staging file are gone


@pytest.mark.parametrize(
    ("status", "worker", "reason"),
    [
        ("succeeded", W, "not_running"),
        ("cancelled", W, "not_running"),
        ("running", "intruder", "wrong_owner"),
    ],
)
def test_a_job_that_may_not_publish_is_refused_and_its_file_removed(
    engine: Engine, storage: LocalStorage, tmp_path: Path, status: str, worker: str, reason: str
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a, worker=worker, status=status)
    with pytest.raises(PublicationRefusedError) as ei:
        run(engine, storage, job, tmp_path)
    assert ei.value.reason == reason and count(engine, "data_asset") == 0 and files(storage) == []


def test_unknown_job_is_target_deleted(engine: Engine, storage: LocalStorage, tmp_path: Path) -> None:
    import uuid

    with pytest.raises(PublicationRefusedError) as ei:
        run(engine, storage, uuid.uuid4(), tmp_path)
    assert ei.value.reason == "target_deleted" and files(storage) == []


def test_contention_exhausts_the_budget_as_a_retryable_error_and_cleans_up(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    """Real: another session holds the AOI row lock (as a deleter would); the publisher gives up cleanly."""
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    with Held(engine) as holder:
        holder.run("SELECT id FROM aoi WHERE id = :a FOR UPDATE", a=a)
        with pytest.raises(PublicationBusyError) as ei:
            run(engine, storage, job, tmp_path, lock_timeout_ms=100, backoff=lambda _n: None)
    assert ei.value.retryable is True and count(engine, "data_asset") == 0 and files(storage) == []
    assert run(engine, storage, job, tmp_path).status == "succeeded"  # the retry (next attempt) succeeds


# ------------------------------------------------------------------ cleanup failure and crash boundaries
class StubbornStorage(LocalStorage):
    """Simulated storage that cannot delete (permissions): the file must survive for the report."""

    def delete(self, key: str) -> None:
        raise OSError("read-only")


def test_unremovable_file_is_retained_and_only_reported(engine: Engine, tmp_path: Path) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a, status="succeeded")  # publication will be refused
    st = StubbornStorage(tmp_path / "s")
    with pytest.raises(PublicationRefusedError):
        run(engine, st, job, tmp_path)
    left = list(st.iter_keys())
    assert len(left) == 1  # bounded cleanup failed; nothing else touched it
    assert reconcile_report(engine, st).unreferenced_files == left  # reported, never deleted
    assert reconcile_report(engine, st).unreferenced_files == left and list(st.iter_keys()) == left


_CRASH = textwrap.dedent(
    """
    import os, sys, uuid
    from pathlib import Path
    from geo_common.db import make_engine
    from geo_common.config import Settings
    from geo_common.storage import LocalStorage
    import geo_connectors.handler as h
    h.publish_asset = lambda *a, **k: os._exit(137)  # the process dies after the file is written, before the commit
    engine = make_engine(os.environ["URL"], pool_size=1)
    s = Settings(_env_file=None, CONNECTOR_MODE="fixture", STORAGE_LOCAL_PATH=sys.argv[1])
    h.run_catalog_search({"start": "2026-01-01", "end": "2026-12-31", "collections": ["synthetic-optical"]},
                         {"job_id": sys.argv[2], "worker_id": "worker-1"}, engine=engine,
                         storage=LocalStorage(sys.argv[1]), settings=s)
    """
)


def test_process_killed_after_the_file_write_leaves_a_reported_orphan_and_a_retry_succeeds(
    engine: Engine, tmp_path: Path
) -> None:
    """Crash boundary (real os._exit at a chosen point): no cleanup can run, so an orphan stays. It is only
    reported; a retry allocates a new key and succeeds; the orphan is never reused or deleted."""
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    root = tmp_path / "crash"
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _CRASH, str(root), str(job)],
        env={**os.environ, "URL": TEST_URL},
        capture_output=True,
        timeout=60,
        cwd=REPO,
        check=False,
    )
    assert p.returncode == 137, p.stderr.decode()[-500:]
    st = LocalStorage(root)
    orphans = list(st.iter_keys())
    assert len(orphans) == 1 and count(engine, "data_asset") == 0
    assert reconcile_report(engine, st).unreferenced_files == orphans and list(st.iter_keys()) == orphans
    out = run_catalog_search(PAYLOAD, context(job), engine=engine, storage=st, settings=settings_for(root))
    assert out.status == "succeeded" and count(engine, "data_asset") == 1
    assert len(list(st.iter_keys())) == 2 and set(orphans) < set(st.iter_keys())  # new key; orphan untouched


# ------------------------------------------------------------------ T5(b): whole worker path, audit hook
_AUDIT = textwrap.dedent(
    """
    import json, os, sys
    events = []
    WATCH = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto")
    from geo_connectors.contracts import in_fetch_window
    def hook(event, args):
        if event in WATCH:
            events.append({"event": event, "args": [str(x) for x in (args[1:] if event in ("socket.connect", "socket.sendto") else args)], "in_fetch_window": in_fetch_window()})
    sys.addaudithook(hook)
    from geo_common.db import make_engine
    from geo_common.config import Settings
    from geo_common.storage import LocalStorage
    import geo_connectors.handler as h
    engine = make_engine(os.environ["URL"], pool_size=1)
    s = Settings(_env_file=None, CONNECTOR_MODE="fixture", STORAGE_LOCAL_PATH=sys.argv[1])
    out = h.run_catalog_search({"start": "2026-01-01", "end": "2026-12-31", "collections": ["synthetic-optical"]},
                               {"job_id": sys.argv[2], "worker_id": "worker-1"}, engine=engine,
                               storage=LocalStorage(sys.argv[1]), settings=s)
    print(json.dumps({"status": out.status, "events": events}))
    """
)


def test_whole_worker_path_connects_only_to_the_test_database_and_never_inside_the_fetch_window(
    engine: Engine, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _AUDIT, str(tmp_path / "audit"), str(job)],
        env={**os.environ, "URL": TEST_URL},
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO,
        check=True,
    )
    doc = json.loads(p.stdout.strip().splitlines()[-1])
    assert doc["status"] == "succeeded" and doc["events"], "the DB connections must have been observed"
    import ast
    import socket

    from sqlalchemy.engine import make_url

    url = make_url(TEST_URL)
    host, port = str(url.host), int(url.port or 5432)
    allowed_ips = {
        ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    }  # what the name means
    for e in doc["events"]:
        assert not e["in_fetch_window"], e  # nothing happens inside Connector.fetch()
        if e["event"] == "socket.connect":
            addr = ast.literal_eval(e["args"][0])
            assert addr[0] in allowed_ips and addr[1] == port, e  # only the test PostgreSQL endpoint
        else:  # name resolution: only the database host name
            assert e["args"][0] == host, e


# ------------------------------------------------------------------ the real runner, spawn child process
def test_runner_runs_the_registered_handler_in_a_child_process(
    engine: Engine,
    queue,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    from runner.handlers import DEFAULT_HANDLERS
    from runner.loop import Runner

    _, a = fixture_aoi(engine)
    for k, v in {**db_env(), "CONNECTOR_MODE": "fixture", "STORAGE_LOCAL_PATH": str(tmp_path / "rs")}.items():
        monkeypatch.setenv(k, v)
    j = queue.enqueue("catalog_search", PAYLOAD, aoi_id=a)
    r = Runner(
        queue, worker_id=W, lease_seconds=30, poll_interval=0.05, job_timeout=60, handlers=DEFAULT_HANDLERS
    )
    assert r.run_once()
    done = queue.get(j.id)
    assert done.status.value == "succeeded", done.error
    assert count(engine, "data_asset") == 1 and len(list(LocalStorage(tmp_path / "rs").iter_keys())) == 1


def test_cleanup_helper_is_what_the_handler_uses_for_its_own_files() -> None:
    import inspect

    import geo_connectors.handler as h

    assert "cleanup_own_files" in inspect.getsource(h) and cleanup_own_files is h.cleanup_own_files
