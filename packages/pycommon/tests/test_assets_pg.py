"""assets_pg: publication verification, idempotency, deletion, tombstone drain, own-file cleanup, reconcile.

Labels: *real* = real database behaviour; *simulated* = injected storage/fault; no concurrency evidence here
(see apps/backend/tests/test_assets_concurrency.py).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from geo_common.assets_pg import (
    AssetJobActiveError,
    AssetNotFoundError,
    PublishRefusedError,
    cleanup_own_files,
    delete_asset,
    drain_tombstones,
    get_asset,
    list_assets,
    load_job_target,
    publish_asset,
    reconcile_report,
    tombstone_pending,
)
from geo_common.storage import LocalStorage

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]
W = "worker-1"


def _running(engine: Engine, add_job: AddJob, aoi: uuid.UUID, worker: str = W) -> uuid.UUID:
    job = add_job(aoi, "running")
    with engine.begin() as c:
        c.execute(text("UPDATE job SET locked_by = :w WHERE id = :j"), {"w": worker, "j": job})
    return job


def _pub(engine: Engine, project: uuid.UUID, aoi: uuid.UUID, job: uuid.UUID, **over: Any) -> Any:
    asset = uuid.uuid4()
    kw: dict[str, Any] = {
        "asset_id": asset, "job_id": job, "worker_id": W, "aoi_id": aoi, "project_id": project,
        "kind": "scene_catalog", "storage_key": f"k/{asset}.json", "media_type": "application/json",
        "size_bytes": 2, "sha256": "0" * 64, "request_hash": "v1:" + "b" * 64,
        "provenance_record": {"source": {"dataset": "d"}}, "backoff": lambda _n: None,
    }  # fmt: skip
    kw.update(over)
    return publish_asset(engine, **kw)


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


# ------------------------------------------------------------------- publication (real)
def test_publish_creates_asset_and_provenance(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> None:
    p, a = make_aoi()
    job = _running(engine, add_job, a)
    res = _pub(engine, p, a, job)
    assert res.created and res.asset.job_id == job and res.asset.provenance == {"source": {"dataset": "d"}}
    assert (_count(engine, "data_asset"), _count(engine, "provenance")) == (1, 1)
    assert get_asset(engine, res.asset.id) == res.asset
    items, total = list_assets(engine, job_id=job)
    assert total == 1 and items[0].id == res.asset.id
    assert list_assets(engine, aoi_id=uuid.uuid4())[1] == 0


@pytest.mark.parametrize("flip", ["status", "worker", "cancel"])
def test_publish_is_refused_unless_running_owned_and_not_cancelled(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, flip: str
) -> None:
    p, a = make_aoi()
    job = _running(engine, add_job, a)
    sql, reason = {
        "status": ("UPDATE job SET status = 'succeeded' WHERE id = :j", "not_running"),
        "worker": ("UPDATE job SET locked_by = 'someone-else' WHERE id = :j", "wrong_owner"),
        "cancel": ("UPDATE job SET cancel_requested = true WHERE id = :j", "cancel_requested"),
    }[flip]
    with engine.begin() as c:
        c.execute(text(sql), {"j": job})
    with pytest.raises(PublishRefusedError) as ei:
        _pub(engine, p, a, job)
    assert ei.value.reason == reason
    assert (_count(engine, "data_asset"), _count(engine, "provenance")) == (0, 0)


def test_terminal_job_never_receives_an_asset_through_the_publisher(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """The real publisher version of the 'late asset on a terminal job' case (T-D7): refused."""
    p, a = make_aoi()
    for status in ("succeeded", "failed", "cancelled", "insufficient_data"):
        job = add_job(a, status)
        with pytest.raises(PublishRefusedError) as ei:
            _pub(engine, p, a, job)
        assert ei.value.reason == "not_running"
    assert _count(engine, "data_asset") == 0


def test_publish_refuses_mismatched_or_deleted_targets(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, a = make_aoi()
    other_p, other_a = make_aoi()
    job = _running(engine, add_job, a)
    with pytest.raises(PublishRefusedError) as e1:
        _pub(engine, other_p, a, job)  # AOI exists but not in that project
    assert e1.value.reason == "target_mismatch"
    with pytest.raises(PublishRefusedError) as e2:
        _pub(engine, other_p, other_a, job)  # job belongs to another AOI
    assert e2.value.reason == "target_mismatch"
    with pytest.raises(PublishRefusedError) as e3:
        _pub(engine, p, a, uuid.uuid4())  # unknown job
    assert e3.value.reason == "target_deleted"
    with pytest.raises(PublishRefusedError) as e4:
        _pub(engine, p, uuid.uuid4(), job)  # unknown AOI
    assert e4.value.reason == "target_deleted"


def test_matching_request_is_an_idempotent_success(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, a = make_aoi()
    job = _running(engine, add_job, a)
    first = _pub(engine, p, a, job)
    again = _pub(engine, p, a, job)  # same (job, kind, request_hash), new asset id/key offered
    assert first.created and not again.created and again.asset.id == first.asset.id
    assert (_count(engine, "data_asset"), _count(engine, "provenance")) == (1, 1)
    other_kind = _pub(engine, p, a, job, kind="dem_clip")
    other_hash = _pub(engine, p, a, job, request_hash="v1:" + "c" * 64)
    assert other_kind.created and other_hash.created and _count(engine, "data_asset") == 3


def test_a_concurrent_identical_request_restarts_and_finds_the_existing_asset(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """Simulated race: the first lookup finds nothing, the INSERT then hits the request uniqueness (23505)."""
    from geo_common.assets_pg import PublishHooks

    p, a = make_aoi()
    job = _running(engine, add_job, a)
    done = threading.Event()

    def rival(_conn: Any) -> None:
        if not done.is_set():
            done.set()
            _pub(engine, p, a, job)  # commits the same request from another session before our INSERT

    res = _pub(engine, p, a, job, hooks=PublishHooks(after_locks=rival))
    assert not res.created and _count(engine, "data_asset") == 1


# ------------------------------------------------------------------- single asset deletion (real) and tombstones
def test_delete_asset_tombstones_in_the_transaction_then_drain_removes_the_file(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, storage: LocalStorage, assets: Any
) -> None:
    _, a = make_aoi()
    job = add_job(a, "succeeded")
    asset, key = assets.add(a, job)
    assert storage.exists(key)
    assert delete_asset(engine, asset) == key
    assert _count(engine, "data_asset") == 0 and _count(engine, "provenance") == 0
    assert tombstone_pending(engine, key) and storage.exists(key)  # the file is removed only after the commit
    report = drain_tombstones(engine, storage)
    assert (report.removed, report.failed, report.remaining) == (1, 0, 0)
    assert not storage.exists(key) and not tombstone_pending(engine, key)


def test_delete_asset_errors(engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any) -> None:
    _, a = make_aoi()
    with pytest.raises(AssetNotFoundError):
        delete_asset(engine, uuid.uuid4())
    running = add_job(a, "running")
    asset, _ = assets.add(a, running)
    with pytest.raises(AssetJobActiveError):
        delete_asset(engine, asset)
    assert _count(engine, "data_asset") == 1 and _count(engine, "storage_tombstone") == 0


def test_drain_missing_file_is_success_and_failures_are_recorded_not_raised(
    engine: Engine, make_aoi: MakeAoi, storage: LocalStorage, assets: Any
) -> None:
    _, a = make_aoi()
    asset, key = assets.add(a, file=False)  # row without a file
    delete_asset(engine, asset)
    assert drain_tombstones(engine, storage).removed == 1  # a missing file counts as success

    asset2, key2 = assets.add(a)
    delete_asset(engine, asset2)

    class Failing(LocalStorage):  # simulated post-commit storage failure
        def delete(self, key: str) -> None:
            raise OSError("disk says no")

    bad = Failing(storage._root)  # type: ignore[attr-defined]
    rep = drain_tombstones(engine, bad)
    assert (rep.removed, rep.failed, rep.remaining) == (0, 1, 1)
    with engine.connect() as c:
        row = c.execute(text("SELECT attempts, last_error FROM storage_tombstone")).one()
    assert row.attempts == 1 and "disk says no" in row.last_error and storage.exists(key2)
    assert drain_tombstones(engine, storage).removed == 1 and not storage.exists(
        key2
    )  # a later run completes it
    assert key


def test_drain_keeps_a_file_that_a_row_still_references(
    engine: Engine, make_aoi: MakeAoi, storage: LocalStorage, assets: Any
) -> None:
    """Defensive re-check: a tombstone for a key that a row references must never delete the file."""
    _, a = make_aoi()
    _, key = assets.add(a)
    with engine.begin() as c:
        c.execute(text("INSERT INTO storage_tombstone (storage_key) VALUES (:k)"), {"k": key})
    rep = drain_tombstones(engine, storage)
    assert (rep.removed, rep.failed) == (0, 1) and storage.exists(key)


def test_replacement_asset_with_a_new_key_is_never_removed_by_an_old_tombstone(
    engine: Engine, make_aoi: MakeAoi, storage: LocalStorage, assets: Any
) -> None:
    _, a = make_aoi()
    old, old_key = assets.add(a)
    delete_asset(engine, old)
    _, new_key = assets.add(a)  # keys are derived from fresh ids: a replacement never reuses the old key
    assert new_key != old_key
    drain_tombstones(engine, storage)
    assert not storage.exists(old_key) and storage.exists(new_key)


def test_concurrent_drains_process_each_tombstone_once(
    engine: Engine, make_aoi: MakeAoi, storage: LocalStorage, assets: Any
) -> None:
    """Real: two drains in two threads share the work through SKIP LOCKED; every file goes exactly once."""
    _, a = make_aoi()
    keys = []
    for _ in range(12):
        asset, key = assets.add(a)
        delete_asset(engine, asset)
        keys.append(key)
    removed: list[int] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            removed.append(drain_tombstones(engine, storage).removed)
        except BaseException as exc:
            errors.append(exc)

    ts = [threading.Thread(target=run) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert not errors and sum(removed) == 12
    assert _count(engine, "storage_tombstone") == 0 and not any(storage.exists(k) for k in keys)


# ------------------------------------------------------------------- own-file cleanup (bounded)
class _Flaky:
    """Storage double that fails its first `n` deletes (simulated)."""

    def __init__(self, n: int) -> None:
        self.n, self.calls, self.staging_calls, self.keys = n, 0, 0, []  # type: ignore[var-annotated]

    def delete(self, key: str) -> None:
        self.calls += 1
        self.keys.append(key)
        if self.calls <= self.n:
            raise OSError("busy")

    def delete_staging(self, key: str) -> None:
        self.staging_calls += 1


def test_cleanup_is_bounded_touches_only_its_own_key_and_reports_failure() -> None:
    ok = _Flaky(0)
    assert cleanup_own_files(ok, "own/key.json", pause=0) and ok.keys == ["own/key.json"]  # type: ignore[arg-type]
    twice = _Flaky(2)
    assert cleanup_own_files(twice, "own/key.json", pause=0) and twice.calls == 3  # type: ignore[arg-type]
    never = _Flaky(99)
    assert not cleanup_own_files(never, "own/key.json", attempts=3, pause=0)  # type: ignore[arg-type]
    assert never.calls == 3 and set(never.keys) == {"own/key.json"}  # bounded; never anything else


def test_cleanup_removes_the_final_file_and_its_staging_file_only(tmp_path: Path) -> None:
    st = LocalStorage(tmp_path)
    st.put("a/own.json", b"x")
    st.put("a/other.json", b"y")
    (tmp_path / ".staging").mkdir(exist_ok=True)
    stray = tmp_path / ".staging" / "stray.part"
    stray.write_bytes(b"z")
    assert cleanup_own_files(st, "a/own.json")
    assert (
        not st.exists("a/own.json") and st.exists("a/other.json") and stray.exists()
    )  # nothing else touched


# ------------------------------------------------------------------- reconcile (report only)
def test_reconcile_reports_and_deletes_nothing(
    engine: Engine, make_aoi: MakeAoi, storage: LocalStorage, assets: Any
) -> None:
    _, a = make_aoi()
    _, kept = assets.add(a)
    missing_id, _ = assets.add(a, file=False)
    storage.put("orphan/unreferenced.json", b"o")
    (storage.open_path("kept").parent / ".staging").mkdir(exist_ok=True)
    old = storage._root / ".staging" / "old.part"  # type: ignore[attr-defined]
    old.write_bytes(b"p")
    import os
    import time

    os.utime(old, (time.time() - 3 * 24 * 3600,) * 2)
    rep = reconcile_report(engine, storage)
    assert rep.unreferenced_files == ["orphan/unreferenced.json"]
    assert rep.rows_missing_file == [str(missing_id)]
    assert [(n, stale) for n, _age, stale in rep.staging_files] == [("old.part", True)]
    assert storage.exists("orphan/unreferenced.json") and old.exists() and storage.exists(kept)  # untouched
    assert reconcile_report(engine, storage).unreferenced_files == ["orphan/unreferenced.json"]  # idempotent


def test_there_is_no_destructive_mode_in_reconcile_code() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts/reconcile_assets.py").read_text()
    for forbidden in ("unlink", "os.remove", "rmtree", ".delete(", "--delete", "--force"):
        assert forbidden not in script, forbidden
    src = (root / "packages/pycommon/src/geo_common/assets_pg.py").read_text()
    body = src[src.index("def reconcile_report") :]
    body = body.split('"""', 2)[2]  # the docstring says "never deletes"; check the code only
    assert "delete" not in body.lower() and "unlink" not in body and "remove" not in body.lower()


def test_load_job_target(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> None:
    p, a = make_aoi()
    job = _running(engine, add_job, a)
    t = load_job_target(engine, job)
    assert t is not None and (t.aoi_id, t.project_id, t.status, t.locked_by) == (a, p, "running", W)
    assert '"Polygon"' in t.aoi_geojson
    assert load_job_target(engine, uuid.uuid4()) is None
