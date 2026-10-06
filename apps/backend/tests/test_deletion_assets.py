"""Deletion with staged assets, provenance, tombstones and the results guard (ADR-0014 §7.5/§8, CP3).

Labels: *real* = real database behaviour; *simulated* = injected fault/storage failure; *policy* = a documented
rule checked in code. Concurrency evidence is in test_assets_concurrency.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app import deletion
from app.deletion import (
    DeletionHooks,
    DeletionOptions,
    HasActiveJobsError,
    HasResultsError,
    NeedsCascadeError,
    NotEmptyError,
    RetryLaterError,
    delete_aoi,
    delete_project,
)
from geo_common.assets_pg import drain_tombstones, pending_tombstones
from geo_common.storage import LocalStorage

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[UUID, UUID]]
AddJob = Callable[..., UUID]


def count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def opts(storage: LocalStorage | None = None, **kw: Any) -> DeletionOptions:
    return DeletionOptions(backoff=lambda _n: None, storage=storage, **kw)


def add_result(engine: Engine, job: UUID) -> None:
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO result (job_id, kind, envelope) VALUES (:j, 'x', '{}'::jsonb)"), {"j": job}
        )


def snapshot(engine: Engine) -> dict[str, int]:
    return {
        t: count(engine, t)
        for t in ("project", "aoi", "job", "result", "data_asset", "provenance", "storage_tombstone")
    }


# ------------------------------------------------------------------ assets, provenance, tombstones (real)
def test_aoi_deletion_removes_job_bound_and_job_less_assets_with_their_provenance(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, storage: LocalStorage
) -> None:
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    _, k1 = assets.add(aoi, job)
    _, k2 = assets.add(
        aoi
    )  # no job: its provenance row has job_id NULL and is not reached by any job cascade
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM provenance WHERE job_id IS NULL")).scalar_one() == 1
    res = delete_aoi(engine, aoi, cascade=True, options=opts(storage))
    assert (res.tombstoned, res.files_pending_cleanup) == (2, 0)
    assert snapshot(engine) | {"project": 0} == {
        "project": 0, "aoi": 0, "job": 0, "result": 0, "data_asset": 0, "provenance": 0, "storage_tombstone": 0,
    }  # fmt: skip
    assert not storage.exists(k1) and not storage.exists(k2)  # files removed after the commit


def test_assets_alone_need_the_cascade_flag(engine: Engine, make_aoi: MakeAoi, assets: Any) -> None:
    _, aoi = make_aoi()
    assets.add(aoi)
    with pytest.raises(NeedsCascadeError) as ei:
        delete_aoi(engine, aoi, cascade=False, options=opts())
    assert (ei.value.jobs, ei.value.assets) == (0, 1) and count(engine, "data_asset") == 1


def test_assets_of_a_cancelled_job_are_removed_by_the_accepted_cascade_path(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, storage: LocalStorage
) -> None:
    """Lifecycle rule: assets published before cancellation stay linked to the cancelled job, and AOI deletion
    still removes them."""
    _, aoi = make_aoi()
    job = add_job(aoi, "cancelled")
    _, key = assets.add(aoi, job)
    delete_aoi(engine, aoi, cascade=True, options=opts(storage))
    assert snapshot(engine)["data_asset"] == 0 and not storage.exists(key)


def test_project_deletion_removes_the_assets_of_all_its_aois(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, storage: LocalStorage
) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi(p)
    other_p, other_a = make_aoi()
    keys = [assets.add(a1, add_job(a1, "succeeded"))[1], assets.add(a2)[1]]
    _, kept = assets.add(other_a)  # another project: untouched
    res = delete_project(engine, p, delete_aois=True, options=opts(storage))
    assert res.tombstoned == 2 and not any(storage.exists(k) for k in keys) and storage.exists(kept)
    assert (count(engine, "data_asset"), count(engine, "project")) == (1, 1) and other_p


def test_post_commit_cleanup_failure_never_fails_the_committed_deletion(
    engine: Engine, make_aoi: MakeAoi, assets: Any, storage: LocalStorage
) -> None:
    """Simulated storage failure after the commit: success with the pending count; a later drain completes."""
    _, aoi = make_aoi()
    _, k1 = assets.add(aoi)
    _, k2 = assets.add(aoi)

    class Failing(LocalStorage):
        def delete(self, key: str) -> None:
            raise OSError("disk says no")

    res = delete_aoi(engine, aoi, cascade=True, options=opts(Failing(storage._root)))  # type: ignore[attr-defined]
    assert (res.tombstoned, res.files_pending_cleanup) == (2, 2)
    assert count(engine, "aoi") == 0 and count(engine, "data_asset") == 0 and storage.exists(k1)
    assert pending_tombstones(engine) == 2
    assert drain_tombstones(engine, storage).remaining == 0 and not storage.exists(k2)


def test_an_unexpected_drain_error_is_swallowed_and_reported_as_pending(
    engine: Engine, make_aoi: MakeAoi, assets: Any, storage: LocalStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, aoi = make_aoi()
    assets.add(aoi)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("drain exploded")

    monkeypatch.setattr(deletion, "drain_tombstones", boom)
    res = delete_aoi(engine, aoi, cascade=True, options=opts(storage))
    assert (res.tombstoned, res.files_pending_cleanup) == (1, 1) and count(engine, "aoi") == 0


# ------------------------------------------------------------------ T-D12 tombstone consistency
def test_tombstones_exist_for_exactly_the_deleted_assets(
    engine: Engine, make_aoi: MakeAoi, assets: Any
) -> None:
    _, a1 = make_aoi()
    _, a2 = make_aoi()
    _, k1 = assets.add(a1)
    _, k2 = assets.add(a2)
    delete_aoi(engine, a1, cascade=True, options=opts())  # no storage: tombstones stay
    with engine.connect() as c:
        tomb = {r[0] for r in c.execute(text("SELECT storage_key FROM storage_tombstone"))}
        rows = {r[0] for r in c.execute(text("SELECT storage_key FROM data_asset"))}
    assert tomb == {k1} and rows == {k2}


def test_a_rolled_back_deletion_leaves_no_tombstone_and_no_lost_row(
    engine: Engine, make_aoi: MakeAoi, assets: Any, storage: LocalStorage
) -> None:
    """Simulated fault after the tombstone insert, on every attempt: the whole transaction is undone."""
    _, aoi = make_aoi()
    _, key = assets.add(aoi)

    def before(label: str) -> None:
        if label == "provenance_delete":
            raise DBAPIError("simulated", {}, Exception({"C": "40P01", "M": "simulated"}))  # type: ignore[arg-type]

    with pytest.raises(RetryLaterError):
        delete_aoi(engine, aoi, cascade=True, options=opts(hooks=DeletionHooks(before_statement=before)))
    assert (
        snapshot(engine)["storage_tombstone"] == 0
        and snapshot(engine)["data_asset"] == 1
        and storage.exists(key)
    )


def test_an_existing_tombstone_for_the_same_key_does_not_abort_the_transaction(
    engine: Engine, make_aoi: MakeAoi, assets: Any
) -> None:
    _, aoi = make_aoi()
    _, key = assets.add(aoi)
    with engine.begin() as c:
        c.execute(text("INSERT INTO storage_tombstone (storage_key) VALUES (:k)"), {"k": key})
    delete_aoi(engine, aoi, cascade=True, options=opts())  # ON CONFLICT DO NOTHING
    assert (count(engine, "storage_tombstone"), count(engine, "data_asset")) == (1, 0)


# ------------------------------------------------------------------ results guard (direct SQL level)
@pytest.mark.parametrize("cascade", [False, True])
def test_results_block_aoi_deletion_whatever_the_flag_and_nothing_changes(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, cascade: bool
) -> None:
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    add_result(engine, job)
    before = snapshot(engine)
    with pytest.raises(HasResultsError):  # has_results, not needs_cascade, even without the flag
        delete_aoi(engine, aoi, cascade=cascade, options=opts())
    assert snapshot(engine) == before and before["result"] == 1


@pytest.mark.parametrize("delete_aois", [False, True])
def test_results_block_project_deletion_whatever_the_flag_and_nothing_changes(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, delete_aois: bool
) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi(p)
    add_result(engine, add_job(a2, "failed"))
    before = snapshot(engine)
    with pytest.raises(HasResultsError):  # has_results, not project_not_empty
        delete_project(engine, p, delete_aois=delete_aois, options=opts())
    assert snapshot(engine) == before and a1


def test_refusal_order_is_active_jobs_then_results_then_cascade_flag(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any
) -> None:
    _, aoi = make_aoi()
    done = add_job(aoi, "succeeded")
    add_result(engine, done)
    assets.add(aoi, done)
    # results + assets, flag absent: results are reported (a flag could never lift them)
    with pytest.raises(HasResultsError):
        delete_aoi(engine, aoi, cascade=False, options=opts())
    # add an active job: the active-job protection comes first, for either flag value
    add_job(aoi, "running")
    for flag in (False, True):
        with pytest.raises(HasActiveJobsError):
            delete_aoi(engine, aoi, cascade=flag, options=opts())
    assert count(engine, "result") == 1 and count(engine, "data_asset") == 1


def test_without_results_the_flag_decides(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "succeeded")
    with pytest.raises(NeedsCascadeError):
        delete_aoi(engine, aoi, cascade=False, options=opts())
    delete_aoi(engine, aoi, cascade=True, options=opts())
    p, a = make_aoi()
    add_job(a, "succeeded")
    with pytest.raises(NotEmptyError):
        delete_project(engine, p, delete_aois=False, options=opts())


def test_result_side_provenance_blocks_but_asset_provenance_does_not(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any
) -> None:
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    assets.add(aoi, job)  # provenance of a staged asset (job_id set): must not trigger the guard
    delete_aoi(engine, aoi, cascade=True, options=opts())
    _, aoi2 = make_aoi()
    job2 = add_job(aoi2, "succeeded")
    with (
        engine.begin() as c
    ):  # a provenance record of the job that no asset owns: treated like a result record
        c.execute(text("INSERT INTO provenance (job_id, record) VALUES (:j, '{}'::jsonb)"), {"j": job2})
    with pytest.raises(HasResultsError):
        delete_aoi(engine, aoi2, cascade=True, options=opts())
    assert count(engine, "provenance") == 1


def test_the_guard_is_per_target_and_the_schema_cascade_is_unchanged(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, with_result = make_aoi()
    _, clean = make_aoi()
    add_result(engine, add_job(with_result, "succeeded"))
    add_job(clean, "succeeded")
    delete_aoi(engine, clean, cascade=True, options=opts())  # unaffected by the other AOI's result
    assert count(engine, "aoi") == 1
    # Characterisation (not policy): result.job_id is still ON DELETE CASCADE in the schema, which is exactly
    # why the application guard above exists. Raw SQL on the job removes its result silently.
    with engine.begin() as c:
        c.execute(text("DELETE FROM job"))
    assert count(engine, "result") == 0


# ------------------------------------------------------------------ results guard (API level)
def test_api_has_results_409_for_both_routes_and_the_result_remains(
    client: TestClient, engine: Engine, make_aoi: MakeAoi, add_job: AddJob, storage: LocalStorage
) -> None:
    client.app.state.storage = storage  # type: ignore[attr-defined]
    p, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    add_result(engine, job)
    for url in (f"/api/v1/aois/{aoi}", f"/api/v1/aois/{aoi}?delete_dependents=true",
                f"/api/v1/projects/{p}", f"/api/v1/projects/{p}?delete_aois=true"):  # fmt: skip
        r = client.delete(url)
        assert r.status_code == 409 and r.json()["error"]["code"] == "has_results", url
    assert snapshot(engine)["result"] == 1 and snapshot(engine)["aoi"] == 1
    add_job(aoi, "queued")  # an active job takes precedence at the API level too
    r = client.delete(f"/api/v1/aois/{aoi}?delete_dependents=true")
    assert r.status_code == 409 and r.json()["error"]["code"] == "has_active_jobs"


def test_api_delete_success_stays_204_with_no_body_and_no_cleanup_header(
    client: TestClient, make_aoi: MakeAoi, assets: Any, storage: LocalStorage
) -> None:
    client.app.state.storage = storage  # type: ignore[attr-defined]
    p, aoi = make_aoi()
    _, key = assets.add(aoi)
    r = client.delete(f"/api/v1/aois/{aoi}?delete_dependents=true")
    assert r.status_code == 204 and r.content == b"" and not storage.exists(key)
    assert not [h for h in r.headers if "pending" in h.lower() or "cleanup" in h.lower()]
    _, aoi2 = make_aoi(p)
    r2 = client.delete(f"/api/v1/projects/{p}?delete_aois=true")
    assert r2.status_code == 204 and r2.content == b"" and aoi2
    assert not [h for h in r2.headers if "pending" in h.lower() or "cleanup" in h.lower()]
