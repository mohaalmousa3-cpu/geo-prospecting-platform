"""Deletion under real concurrency (ADR-0014 §7.5 revision 5; job level).

Evidence type: *real* database sessions synchronised through observable lock state (`pg_blocking_pids`), with a
bounded timeout on every wait and no `sleep` guessing. Where a case needs a worker that holds the key-share lock
a foreign-key check would take on a job row, that lock holder is **emulated** with an explicit
`SELECT … FOR KEY SHARE`; the real asset-insert variants arrive with migration 0005 (not part of this checkpoint).
These tests are deterministic design checks, not a proof that deadlocks are impossible.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest
from db_concurrency import Bg, Gate, Held, wait_blocked_by
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.deletion import (
    DeletionHooks,
    DeletionOptions,
    HasActiveJobsError,
    NotEmptyError,
    RetryLaterError,
    TargetNotFoundError,
    delete_aoi,
    delete_project,
)
from geo_common.queue import JobTargetNotFoundError
from geo_common.queue_pg import PostgresJobQueue
from geo_common.transactions import constraint_name, sqlstate

pytestmark = [pytest.mark.integration, pytest.mark.timeout(60)]

MakeAoi = Callable[..., tuple[UUID, UUID]]
AddJob = Callable[..., UUID]


def count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def paused(gate: Gate, at: str = "after_parent_lock", **kw: object) -> DeletionOptions:
    return DeletionOptions(hooks=DeletionHooks(**{at: gate}), backoff=lambda _n: None, **kw)  # type: ignore[arg-type]


# ------------------------------------------------------------------ T-D2 job insert vs delete, both orders
def test_insert_first_then_delete_sees_the_new_job(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi
) -> None:
    _, aoi = make_aoi()
    with Held(engine) as s:
        s.run(
            "INSERT INTO job (type, aoi_id, project_id) "
            "SELECT 'catalog_search', id, project_id FROM aoi WHERE id=:a",
            a=aoi,
        )  # uncommitted: holds a key-share lock on the AOI row through the FK check
        d = Bg(
            lambda: delete_aoi(engine, aoi, cascade=True, options=DeletionOptions(backoff=lambda _n: None))
        )
        wait_blocked_by(engine, s.pid, "deleter waiting for the AOI row lock")
        s.commit()
    assert isinstance(d.exception(), HasActiveJobsError)  # the committed queued job is seen after the lock
    assert (count(engine, "aoi"), count(engine, "job")) == (1, 1)


def test_delete_first_then_insert_fails_its_fk_and_is_translated(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi
) -> None:
    _, aoi = make_aoi()
    gate = Gate()
    d = Bg(lambda: delete_aoi(engine, aoi, cascade=False, options=paused(gate)))
    holder = gate.wait_reached()
    ins = Bg(lambda: queue.enqueue("catalog_search", aoi_id=aoi))
    wait_blocked_by(engine, holder, "enqueue waiting for the AOI key-share lock")
    gate.release.set()
    d.result()
    assert isinstance(ins.exception(), JobTargetNotFoundError)
    assert (count(engine, "aoi"), count(engine, "job")) == (0, 0)


# ------------------------------------------------------------------ T-D3 claim vs delete
def test_claim_before_delete_makes_the_job_running_and_refuses_deletion(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "queued")
    assert queue.claim("w1", 30) is not None
    with pytest.raises(HasActiveJobsError):
        delete_aoi(engine, aoi, cascade=True)
    assert count(engine, "aoi") == 1


def test_claim_while_the_deleter_holds_the_aoi_still_succeeds_and_deletion_is_refused(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "queued")
    gate = Gate()
    d = Bg(lambda: delete_aoi(engine, aoi, cascade=True, options=paused(gate)))
    gate.wait_reached()
    claimed = queue.claim("w1", 30)  # a claim takes only the job row lock: it is not blocked by the AOI lock
    gate.release.set()
    assert claimed is not None and claimed.status.value == "running"
    assert isinstance(d.exception(), HasActiveJobsError)
    assert (count(engine, "aoi"), count(engine, "job")) == (1, 1)


# ------------------------------------------------------------------ T-D5 negative control (the cycle of the lock-all-jobs variant)
def test_negative_control_lock_all_jobs_with_waiting_deadlocks(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """The r3 shape: deleter holds the AOI and waits for the job; the 'asset insert' holds the job key-share
    lock and then needs the AOI key-share lock. PostgreSQL must break the cycle with 40P01, proving the harness
    can see the cycle that revision 5 avoids by not waiting for job rows (the lock holder is emulated)."""
    _, aoi = make_aoi()
    job = add_job(aoi, "running")
    with Held(engine) as d_s, Held(engine) as w_s:
        d_s.run("SELECT id FROM aoi WHERE id=:a FOR UPDATE", a=aoi)
        w_s.run("SELECT 1 FROM job WHERE id=:j FOR KEY SHARE", j=job)
        d = Bg(lambda: d_s.run("SELECT id FROM job WHERE aoi_id=:a ORDER BY id FOR UPDATE", a=aoi))
        wait_blocked_by(engine, w_s.pid, "r3-style deleter waiting for the job row")
        w = Bg(lambda: w_s.run("SELECT 1 FROM aoi WHERE id=:a FOR KEY SHARE", a=aoi))
        errs = [x for x in (d.exception(), w.exception()) if x is not None]
        assert len(errs) == 1 and isinstance(errs[0], DBAPIError) and sqlstate(errs[0]) == "40P01", errs


# ------------------------------------------------------------------ T-D6 / T-D7 corrected deleter vs an emulated asset-insert lock holder
def test_deleter_does_not_wait_for_a_worker_holding_a_running_job(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    job = add_job(aoi, "running")
    with Held(engine) as w:
        w.run("SELECT 1 FROM job WHERE id=:j FOR KEY SHARE", j=job)  # emulated FK-B lock
        done_before_worker_finished = False
        with pytest.raises(HasActiveJobsError):  # returns while the worker transaction is still open
            delete_aoi(engine, aoi, cascade=True, options=DeletionOptions(backoff=lambda _n: None))
        done_before_worker_finished = w.tx.is_active
        assert done_before_worker_finished
        w.run("SELECT 1 FROM aoi WHERE id=:a FOR KEY SHARE", a=aoi)  # the worker proceeds normally
        w.commit()
    assert (count(engine, "aoi"), count(engine, "job")) == (1, 1)


@pytest.mark.parametrize("order", ["job_then_aoi", "aoi_then_job"])
def test_late_lock_holder_on_a_terminal_job_gives_retry_later_not_a_deadlock(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, order: str
) -> None:
    """Both foreign-key lock orders of an emulated late asset insert on a terminal job.

    job_then_aoi: the worker holds the job; the deleter's NOWAIT job lock is refused (55P03) on every attempt.
    aoi_then_job: the worker holds the AOI key-share lock; the deleter's AOI lock times out (55P03).
    Either way: 503-equivalent after the single budget, no 40P01 anywhere, nothing deleted, the worker finishes.
    """
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    first, second = (
        ("SELECT 1 FROM job WHERE id=:j FOR KEY SHARE", "SELECT 1 FROM aoi WHERE id=:a FOR KEY SHARE")
        if order == "job_then_aoi"
        else ("SELECT 1 FROM aoi WHERE id=:a FOR KEY SHARE", "SELECT 1 FROM job WHERE id=:j FOR KEY SHARE")
    )
    # job_then_aoi: a deleter that WAITED for the job row would block here (long lock_timeout) until the bounded
    # join fails the test; with NOWAIT it is refused immediately. aoi_then_job: the AOI wait is bounded (200 ms).
    timeout_ms = 60_000 if order == "job_then_aoi" else 200
    with Held(engine) as w:
        w.run(first, j=job, a=aoi)
        d = Bg(
            lambda: delete_aoi(
                engine,
                aoi,
                cascade=True,
                options=DeletionOptions(lock_timeout_ms=timeout_ms, backoff=lambda _n: None),
            )
        )
        assert isinstance(d.exception(), RetryLaterError)  # bounded join: fails if the deleter waits
        w.run(second, j=job, a=aoi)  # no deadlock: the worker is never blocked by the deleter
        w.commit()
    assert (count(engine, "aoi"), count(engine, "job")) == (1, 1)


# ------------------------------------------------------------------ T-D8 project delete vs AOI create / job insert
def test_aoi_insert_first_then_project_delete_sees_the_aoi(engine: Engine, make_aoi: MakeAoi) -> None:
    p, _ = make_aoi()
    with Held(engine) as s:
        s.run(
            "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) VALUES "
            "(:p, 'late', ST_GeomFromText('POLYGON((2 2,3 2,3 3,2 3,2 2))', 4326), 'polygon', 1, 4, 'EPSG:32631')",
            p=p,
        )
        d = Bg(
            lambda: delete_project(
                engine, p, delete_aois=False, options=DeletionOptions(backoff=lambda _n: None)
            )
        )
        wait_blocked_by(engine, s.pid, "project deleter waiting for the project row lock")
        s.commit()
    exc = d.exception()
    assert isinstance(exc, NotEmptyError) and exc.aoi_count == 2
    assert (count(engine, "project"), count(engine, "aoi")) == (1, 2)


def test_project_delete_first_then_aoi_insert_fails_on_the_project_fk(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    p, a = make_aoi()
    gate = Gate()
    d = Bg(lambda: delete_project(engine, p, delete_aois=True, options=paused(gate)))
    holder = gate.wait_reached()

    def insert() -> None:
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) VALUES "
                    "(:p, 'late', ST_GeomFromText('POLYGON((2 2,3 2,3 3,2 3,2 2))', 4326), 'polygon', 1, 4, 'EPSG:32631')"
                ),
                {"p": p},
            )

    ins = Bg(insert)
    wait_blocked_by(engine, holder, "AOI insert waiting for the project key-share lock")
    gate.release.set()
    d.result()
    exc = ins.exception()
    assert isinstance(exc, DBAPIError) and (sqlstate(exc), constraint_name(exc)) == (
        "23503",
        "aoi_project_id_fkey",
    )
    assert (count(engine, "project"), count(engine, "aoi")) == (0, 0) and a


def test_project_delete_first_then_job_insert_in_a_child_aoi_is_translated(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi
) -> None:
    p, aoi = make_aoi()
    gate = Gate()
    d = Bg(lambda: delete_project(engine, p, delete_aois=True, options=paused(gate)))
    holder = gate.wait_reached()
    ins = Bg(lambda: queue.enqueue("catalog_search", aoi_id=aoi))
    wait_blocked_by(engine, holder, "enqueue waiting for the child AOI lock held by the project deleter")
    gate.release.set()
    d.result()
    assert isinstance(ins.exception(), JobTargetNotFoundError)
    assert (count(engine, "project"), count(engine, "aoi"), count(engine, "job")) == (0, 0, 0)


# ------------------------------------------------------------------ T-D9 concurrent deleters end in a serial-equivalent state
def test_project_deleter_holding_locks_makes_an_aoi_deleter_find_nothing(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    p, a1 = make_aoi()
    make_aoi(p)
    gate = Gate()
    pd = Bg(lambda: delete_project(engine, p, delete_aois=True, options=paused(gate)))
    holder = gate.wait_reached()
    ad = Bg(lambda: delete_aoi(engine, a1, cascade=False, options=DeletionOptions(backoff=lambda _n: None)))
    wait_blocked_by(engine, holder, "AOI deleter waiting for the AOI row held by the project deleter")
    gate.release.set()
    pd.result()
    assert isinstance(ad.exception(), TargetNotFoundError)
    assert (count(engine, "project"), count(engine, "aoi")) == (0, 0)


def test_aoi_deleter_holding_an_aoi_does_not_deadlock_with_a_project_deleter(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    p, a1 = make_aoi()
    make_aoi(p)
    gate = Gate()
    ad = Bg(lambda: delete_aoi(engine, a1, cascade=False, options=paused(gate)))
    holder = gate.wait_reached()
    pd = Bg(
        lambda: delete_project(engine, p, delete_aois=True, options=DeletionOptions(backoff=lambda _n: None))
    )
    wait_blocked_by(engine, holder, "project deleter waiting for the AOI row held by the AOI deleter")
    gate.release.set()
    ad.result()
    pd.result()  # a1 is gone (skipped by the re-evaluated lock statement); the rest is deleted
    assert (count(engine, "project"), count(engine, "aoi")) == (0, 0)


def test_two_project_deleters_serialise_on_the_project_row(engine: Engine, make_aoi: MakeAoi) -> None:
    p, _ = make_aoi()
    gate = Gate()
    first = Bg(lambda: delete_project(engine, p, delete_aois=True, options=paused(gate)))
    holder = gate.wait_reached()
    second = Bg(
        lambda: delete_project(engine, p, delete_aois=True, options=DeletionOptions(backoff=lambda _n: None))
    )
    wait_blocked_by(engine, holder, "second project deleter waiting for the project row")
    gate.release.set()
    first.result()
    assert isinstance(second.exception(), TargetNotFoundError)


# ------------------------------------------------------------------ T-D10 enqueue (advisory lock) vs deleter
def test_enqueue_holding_the_advisory_lock_does_not_deadlock_with_a_deleter(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi
) -> None:
    _, aoi = make_aoi()
    gate = Gate()
    d = Bg(lambda: delete_aoi(engine, aoi, cascade=False, options=paused(gate)))
    holder = gate.wait_reached()
    e1 = Bg(
        lambda: queue.enqueue("catalog_search", aoi_id=aoi)
    )  # takes the advisory lock, then waits for the AOI
    wait_blocked_by(engine, holder, "enqueue waiting for the AOI while holding the advisory lock")
    e2 = Bg(lambda: queue.enqueue("noop"))  # head-of-line: waits behind the advisory lock (liveness only)
    gate.release.set()
    d.result()  # the deleter never needs the advisory lock, so it completes
    assert isinstance(e1.exception(), JobTargetNotFoundError)
    assert e2.result().type == "noop"
