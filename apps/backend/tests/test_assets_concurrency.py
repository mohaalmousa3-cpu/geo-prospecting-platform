"""Asset publication, cancellation and deletion under real concurrency (ADR-0014 §7.5/§8; CP3).

Evidence types, kept apart:
* *real publisher*: `geo_common.assets_pg.publish_asset` runs in a real session and is paused at a test seam
  (`PublishHooks`) while real locks are held;
* *raw SQL*: a test session issues the asset INSERT itself. The two relevant lock orders are *controlled* by an
  explicit pre-lock (aoi first, or job first); the order in which PostgreSQL fires its own foreign-key checks is
  not inferred. The foreign-key checks still run for real inside the INSERT.
Synchronisation: `pg_blocking_pids` (a session is blocked by the holder's pid), bounded waits, no sleeps.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from db_concurrency import Bg, Gate, Held, wait_blocked_by
from sqlalchemy import Engine, text

from app.deletion import (
    DeletionHooks,
    DeletionOptions,
    HasActiveJobsError,
    RetryLaterError,
    delete_aoi,
)
from geo_common.assets_pg import PublishHooks, publish_asset
from geo_common.queue import JobStatus
from geo_common.queue_pg import PostgresJobQueue
from geo_common.storage import LocalStorage

pytestmark = [pytest.mark.integration, pytest.mark.timeout(60)]
MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]
W = "worker-1"


def count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def running(engine: Engine, add_job: AddJob, aoi: uuid.UUID) -> uuid.UUID:
    job = add_job(aoi, "running")
    with engine.begin() as c:
        c.execute(text("UPDATE job SET locked_by = :w WHERE id = :j"), {"w": W, "j": job})
    return job


def publish(engine: Engine, project: uuid.UUID, aoi: uuid.UUID, job: uuid.UUID, **kw: Any) -> Any:
    asset = uuid.uuid4()
    return publish_asset(
        engine,
        asset_id=asset,
        job_id=job,
        worker_id=W,
        aoi_id=aoi,
        project_id=project,
        kind="scene_catalog",
        storage_key=f"k/{asset}.json",
        media_type="application/json",
        size_bytes=2,
        sha256="0" * 64,
        request_hash="v1:" + "d" * 64,
        provenance_record={"source": {"dataset": "d"}},
        backoff=lambda _n: None,
        **kw,
    )


def deleter_options(**kw: Any) -> DeletionOptions:
    return DeletionOptions(backoff=lambda _n: None, **kw)


# ------------------------------------------------------------------ T-D6 real: publisher vs deleter
def test_td6_real_publisher_holds_aoi_then_job_and_the_deleter_waits_then_refuses(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """Publisher (AOI key-share → job share → INSERT) paused before commit; the deleter starts meanwhile.

    Expected: the deleter blocks on the AOI row lock held by the publisher, resumes after the commit, sees the
    still-running job and refuses (has_active_jobs). No deadlock (no 40P01 / RetryLater), the asset exists."""
    p, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    gate = Gate()
    pub = Bg(lambda: publish(engine, p, aoi, job, hooks=PublishHooks(after_insert=gate)))
    holder = gate.wait_reached()
    d = Bg(lambda: delete_aoi(engine, aoi, cascade=True, options=deleter_options()))
    wait_blocked_by(engine, holder, "deleter waiting for the AOI row held by the publisher")
    gate.release.set()
    assert pub.result().created
    assert isinstance(d.exception(), HasActiveJobsError)
    assert (count(engine, "data_asset"), count(engine, "aoi")) == (1, 1)


def test_td6_real_deleter_first_then_publisher_waits_and_publishes_after_the_refusal(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    gate = Gate()
    d = Bg(
        lambda: delete_aoi(
            engine, aoi, cascade=True, options=deleter_options(hooks=DeletionHooks(after_parent_lock=gate))
        )
    )
    holder = gate.wait_reached()
    pub = Bg(lambda: publish(engine, p, aoi, job))
    wait_blocked_by(engine, holder, "publisher waiting for the AOI key-share lock")
    gate.release.set()
    assert isinstance(d.exception(), HasActiveJobsError)  # the deleter saw the running job and rolled back
    assert pub.result().created and count(engine, "data_asset") == 1


@pytest.mark.parametrize("order", ["aoi_then_job", "job_then_aoi"])
def test_td6_raw_insert_in_both_controlled_lock_orders_never_deadlocks(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, order: str
) -> None:
    """Raw SQL path with the first lock chosen by the test; the INSERT's own FK checks supply the rest."""
    _, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    with Held(engine) as w:
        first = "SELECT 1 FROM aoi WHERE id = :a FOR KEY SHARE" if order == "aoi_then_job" else (
            "SELECT 1 FROM job WHERE id = :j FOR KEY SHARE")  # fmt: skip
        w.run(first, a=aoi, j=job)
        if order == "aoi_then_job":
            assets.insert(w.conn, aoi, job, file=False)  # worker now holds the AOI and (via FK-B) the job
            d = Bg(lambda: delete_aoi(engine, aoi, cascade=True, options=deleter_options()))
            wait_blocked_by(engine, w.pid, "deleter waiting for the AOI row held by the raw INSERT")
            w.commit()
            assert isinstance(d.exception(), HasActiveJobsError)
        else:
            # the worker holds only the job so far: the deleter takes the AOI, reads the running job and refuses
            # immediately, WITHOUT waiting for the worker (it returns while the worker transaction is open)
            with pytest.raises(HasActiveJobsError):
                delete_aoi(engine, aoi, cascade=True, options=deleter_options())
            assets.insert(w.conn, aoi, job, file=False)  # the worker's FK-A check can take the AOI lock now
            w.commit()
    assert count(engine, "data_asset") == 1 and count(engine, "aoi") == 1


# ------------------------------------------------------------------ T-D7 real: assets on terminal jobs
def test_td7_the_real_publisher_refuses_a_terminal_job_while_a_deleter_is_unaffected(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    from geo_common.assets_pg import PublishRefusedError

    p, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    with pytest.raises(PublishRefusedError):
        publish(engine, p, aoi, job)
    delete_aoi(engine, aoi, cascade=True, options=deleter_options())
    assert count(engine, "aoi") == 0


@pytest.mark.parametrize("order", ["aoi_then_job", "job_then_aoi"])
def test_td7_raw_late_asset_on_a_terminal_job_gives_retry_later_never_a_deadlock(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, order: str
) -> None:
    """A raw INSERT bypasses the publisher, so a 'late asset on a terminal job' can exist. The deleter must fail
    fast (NOWAIT) or after the bounded lock timeout, never deadlock; afterwards the system recovers."""
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    timeout_ms = 200 if order == "aoi_then_job" else 60_000  # job_then_aoi must fail fast, not by timeout
    with Held(engine) as w:
        if order == "aoi_then_job":
            w.run("SELECT 1 FROM aoi WHERE id = :a FOR KEY SHARE", a=aoi)
            assets.insert(w.conn, aoi, job, file=False)
        else:
            w.run("SELECT 1 FROM job WHERE id = :j FOR KEY SHARE", j=job)
        d = Bg(
            lambda: delete_aoi(engine, aoi, cascade=True, options=deleter_options(lock_timeout_ms=timeout_ms))
        )
        assert isinstance(d.exception(), RetryLaterError)  # bounded join: fails if the deleter waits
        if order == "job_then_aoi":
            assets.insert(w.conn, aoi, job, file=False)  # the worker is never blocked by the failed deleter
        w.commit()
    assert count(engine, "data_asset") == 1 and count(engine, "aoi") == 1
    delete_aoi(
        engine, aoi, cascade=True, options=deleter_options()
    )  # recovery: the cascade removes the asset
    assert (count(engine, "data_asset"), count(engine, "aoi")) == (0, 0)


# ------------------------------------------------------------------ publication versus cancellation (real)
def test_cancel_during_publication_waits_for_it_and_the_asset_stays_linked_to_the_cancelled_job(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi, add_job: AddJob, storage: LocalStorage
) -> None:
    """Publisher paused with the job row share-locked; `cancel()` must wait (its UPDATE conflicts with the share
    lock). Publication completes first; then the job is completed as cancelled; the asset remains linked to it
    and the accepted AOI deletion still removes it (policy of 2026-10-05)."""
    p, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    gate = Gate()
    pub = Bg(lambda: publish(engine, p, aoi, job, hooks=PublishHooks(after_locks=gate)))
    holder = gate.wait_reached()
    cancel = Bg(lambda: queue.cancel(job))
    wait_blocked_by(engine, holder, "cancel() waiting for the share lock on the job row")
    gate.release.set()
    published = pub.result()
    assert published.created and cancel.result().cancel_requested is True
    assert queue.complete(job, W, JobStatus.CANCELLED, "cancelled by request")
    with engine.connect() as c:
        row = c.execute(
            text("SELECT j.status, a.job_id FROM job j JOIN data_asset a ON a.job_id = j.id")
        ).one()
    assert (row.status, row.job_id) == ("cancelled", job)  # the asset is linked to the cancelled job
    delete_aoi(engine, aoi, cascade=True, options=deleter_options(storage=storage))
    assert (count(engine, "data_asset"), count(engine, "provenance")) == (0, 0)  # reachable by the cascade


def test_cancel_requested_before_the_publication_transaction_refuses_it(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    from geo_common.assets_pg import PublishRefusedError

    p, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    queue.cancel(job)  # running job: cancel_requested is recorded
    with pytest.raises(PublishRefusedError) as ei:
        publish(engine, p, aoi, job)
    assert ei.value.reason == "cancel_requested" and count(engine, "data_asset") == 0


def test_deleter_in_progress_and_cancel_request_do_not_deadlock(
    engine: Engine, queue: PostgresJobQueue, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """Deleter holds the AOI (paused); a cancel request (job row UPDATE) proceeds independently; the deleter
    then refuses because the job is still active. No lock cycle."""
    _, aoi = make_aoi()
    job = running(engine, add_job, aoi)
    gate = Gate()
    d = Bg(
        lambda: delete_aoi(
            engine, aoi, cascade=True, options=deleter_options(hooks=DeletionHooks(after_parent_lock=gate))
        )
    )
    gate.wait_reached()
    assert queue.cancel(job).cancel_requested is True  # not blocked by the AOI lock
    gate.release.set()
    assert isinstance(d.exception(), HasActiveJobsError)


# ------------------------------------------------------------------ asset and provenance rows are locked NOWAIT too
@pytest.mark.parametrize("held", ["asset_row", "provenance_row"])
def test_deleter_fails_fast_on_a_busy_asset_or_provenance_row(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, assets: Any, held: str
) -> None:
    """Real: another session (e.g. a single-asset deletion in progress) holds the asset or provenance row.
    The deleter must not wait for it (long lock_timeout + bounded join): it ends in RetryLater, then recovers."""
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    asset, _ = assets.add(aoi, job)
    sql = {
        "asset_row": "SELECT id FROM data_asset WHERE id = :i FOR UPDATE",
        "provenance_row": "SELECT p.id FROM provenance p JOIN data_asset a ON a.provenance_id = p.id "
        "WHERE a.id = :i FOR UPDATE OF p",
    }[held]
    with Held(engine) as other:
        other.run(sql, i=asset)
        d = Bg(lambda: delete_aoi(engine, aoi, cascade=True, options=deleter_options(lock_timeout_ms=60_000)))
        assert isinstance(d.exception(), RetryLaterError)  # bounded join: fails if the deleter waits
    assert (count(engine, "data_asset"), count(engine, "aoi")) == (1, 1)  # nothing changed
    delete_aoi(engine, aoi, cascade=True, options=deleter_options())
    assert (count(engine, "data_asset"), count(engine, "aoi")) == (0, 0)


def test_a_waiting_publisher_holds_no_job_lock_because_it_takes_the_aoi_first(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """Real publisher, lock-order evidence. The deleter is paused holding the AOI of a *terminal* job; the
    publisher starts and must wait on the AOI. Because the publisher takes the AOI before the job, it waits
    holding no job lock, so the deleter's NOWAIT job lock succeeds on its FIRST attempt (one `aoi_lock`
    statement). A publisher that took the job first would make that lock fail and force a restart."""
    p, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    gate = Gate()
    attempts: list[str] = []

    def count_attempts(label: str) -> None:
        if label == "aoi_lock":
            attempts.append(label)

    hooks = DeletionHooks(after_parent_lock=gate, before_statement=count_attempts)
    d = Bg(lambda: delete_aoi(engine, aoi, cascade=True, options=deleter_options(hooks=hooks)))
    holder = gate.wait_reached()
    from geo_common.assets_pg import PublishRefusedError

    pub = Bg(lambda: publish(engine, p, aoi, job))
    wait_blocked_by(engine, holder, "publisher waiting for the AOI row held by the deleter")
    gate.release.set()
    d.result()
    assert len(attempts) == 1  # no restart: the waiting publisher held nothing the deleter needs
    exc = pub.exception()
    assert (
        isinstance(exc, PublishRefusedError) and exc.reason == "target_deleted"
    )  # the AOI was deleted meanwhile
    assert count(engine, "aoi") == 0
