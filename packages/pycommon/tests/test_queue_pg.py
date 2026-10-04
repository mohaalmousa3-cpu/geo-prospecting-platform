"""Mandatory queue tests (ADR-0007): concurrency, lease renewal, retry, recovery, cancel."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, text

from geo_common.queue import JobNotFoundError, JobStatus, QueueFullError
from geo_common.queue_pg import PostgresJobQueue

pytestmark = pytest.mark.integration


def expire_lease(engine: Engine, job_id: object) -> None:
    with engine.begin() as c:
        c.execute(
            text("UPDATE job SET lease_expires_at = now() - interval '1 second' WHERE id=:i"),
            {"i": job_id},
        )


def test_enqueue_and_get(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("noop", {"a": 1})
    got = queue.get(j.id)
    assert got.status is JobStatus.QUEUED and got.payload == {"a": 1} and got.attempts == 0
    assert got.max_attempts == 2


def test_get_missing(queue: PostgresJobQueue) -> None:
    from uuid import uuid4

    with pytest.raises(JobNotFoundError):
        queue.get(uuid4())


def test_queue_full(engine: Engine) -> None:
    q = PostgresJobQueue(engine, max_queued_jobs=3, default_max_attempts=2)
    for _ in range(3):
        q.enqueue("noop")
    with pytest.raises(QueueFullError):
        q.enqueue("noop")
    # running jobs do not count against MAX_QUEUED_JOBS
    q.claim("w", 60)
    q.enqueue("noop")


def test_queue_full_is_race_safe(engine: Engine) -> None:
    q = PostgresJobQueue(engine, max_queued_jobs=5, default_max_attempts=2)

    def attempt(_: int) -> bool:
        try:
            q.enqueue("noop")
            return True
        except QueueFullError:
            return False

    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(attempt, range(40)))
    assert sum(results) == 5


def test_priority_then_age(queue: PostgresJobQueue) -> None:
    low = queue.enqueue("noop", priority=0)
    old_hi = queue.enqueue("noop", priority=5)
    new_hi = queue.enqueue("noop", priority=5)
    order = [queue.claim("w", 60).id for _ in range(3)]  # type: ignore[union-attr]
    assert order == [old_hi.id, new_hi.id, low.id]
    assert queue.claim("w", 60) is None


def test_concurrent_claim_never_double_claims(engine: Engine) -> None:
    q = PostgresJobQueue(engine, max_queued_jobs=100, default_max_attempts=2)
    ids = {q.enqueue("noop").id for _ in range(50)}
    barrier = threading.Barrier(12)
    claimed: list[object] = []
    lock = threading.Lock()

    def worker(n: int) -> None:
        barrier.wait()
        while (job := q.claim(f"w{n}", 60)) is not None:
            with lock:
                claimed.append(job.id)

    with ThreadPoolExecutor(12) as ex:
        list(ex.map(worker, range(12)))
    assert len(claimed) == 50 and set(claimed) == ids  # each exactly once


def test_claim_sets_lease_and_attempts(queue: PostgresJobQueue) -> None:
    queue.enqueue("noop")
    j = queue.claim("w1", 30)
    assert j is not None and j.status is JobStatus.RUNNING
    assert j.attempts == 1 and j.locked_by == "w1" and j.lease_expires_at is not None


def test_heartbeat_renews_lease_and_rejects_non_owner(queue: PostgresJobQueue, engine: Engine) -> None:
    queue.enqueue("noop")
    j = queue.claim("w1", 5)
    assert j is not None and j.lease_expires_at is not None
    hb = queue.heartbeat(j.id, "w1", 600)
    assert hb.owned and not hb.cancel_requested
    renewed = queue.get(j.id).lease_expires_at
    assert renewed is not None and (renewed - j.lease_expires_at).total_seconds() > 500
    assert not queue.heartbeat(j.id, "intruder", 600).owned


def test_renewed_lease_prevents_recovery(queue: PostgresJobQueue, engine: Engine) -> None:
    queue.enqueue("noop")
    j = queue.claim("w1", 1)
    assert j is not None
    time.sleep(0.6)
    assert queue.heartbeat(j.id, "w1", 60).owned
    time.sleep(0.8)  # original 1s lease would have expired by now
    assert queue.requeue_expired() == 0
    assert queue.get(j.id).status is JobStatus.RUNNING


def test_expired_lease_is_requeued_and_stale_worker_cannot_finish(
    queue: PostgresJobQueue, engine: Engine
) -> None:
    queue.enqueue("noop")
    j = queue.claim("crashed", 60)
    assert j is not None
    expire_lease(engine, j.id)
    assert queue.requeue_expired() == 1
    again = queue.get(j.id)
    assert again.status is JobStatus.QUEUED and again.locked_by is None and again.attempts == 1
    j2 = queue.claim("healthy", 60)
    assert j2 is not None and j2.id == j.id and j2.attempts == 2
    # the crashed worker comes back from the dead: must be refused everywhere
    assert not queue.complete(j.id, "crashed")
    assert not queue.fail(j.id, "crashed", "late")
    assert not queue.heartbeat(j.id, "crashed", 60).owned
    assert queue.complete(j.id, "healthy")
    assert queue.get(j.id).status is JobStatus.SUCCEEDED


def test_attempt_limit_exhausted_fails_job(queue: PostgresJobQueue, engine: Engine) -> None:
    queue.enqueue("noop", max_attempts=2)
    for n in range(2):
        j = queue.claim(f"w{n}", 60)
        assert j is not None
        expire_lease(engine, j.id)
        assert queue.requeue_expired() == 1
    final = queue.get(j.id)
    assert final.status is JobStatus.FAILED and final.attempts == 2
    assert final.error and "max attempts" in final.error and final.finished_at is not None
    assert queue.claim("w", 60) is None


def test_retryable_failure_requeues_until_exhausted(queue: PostgresJobQueue) -> None:
    queue.enqueue("noop", max_attempts=2)
    j = queue.claim("w", 60)
    assert j is not None and queue.fail(j.id, "w", "transient", retryable=True)
    assert queue.get(j.id).status is JobStatus.QUEUED
    j = queue.claim("w", 60)
    assert j is not None and queue.fail(j.id, "w", "transient again", retryable=True)
    last = queue.get(j.id)
    assert last.status is JobStatus.FAILED and last.error == "transient again"


def test_non_retryable_failure_is_terminal(queue: PostgresJobQueue) -> None:
    queue.enqueue("noop")
    j = queue.claim("w", 60)
    assert j is not None and queue.fail(j.id, "w", "boom")
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and f.error == "boom" and f.attempts == 1


def test_complete_insufficient_data(queue: PostgresJobQueue) -> None:
    queue.enqueue("noop")
    j = queue.claim("w", 60)
    assert j is not None
    assert queue.complete(j.id, "w", JobStatus.INSUFFICIENT_DATA, "no scenes")
    d = queue.get(j.id)
    assert d.status is JobStatus.INSUFFICIENT_DATA and d.error == "no scenes"
    with pytest.raises(ValueError):
        queue.complete(j.id, "w", JobStatus.CANCELLED)


def test_cancel_queued_is_immediate(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("noop")
    c = queue.cancel(j.id)
    assert c.status is JobStatus.CANCELLED and c.finished_at is not None
    assert queue.claim("w", 60) is None


def test_cancel_running_sets_flag_and_heartbeat_reports_it(queue: PostgresJobQueue) -> None:
    queue.enqueue("noop")
    j = queue.claim("w", 60)
    assert j is not None
    assert queue.cancel(j.id).status is JobStatus.RUNNING
    assert queue.heartbeat(j.id, "w", 60).cancel_requested
    assert queue.fail(j.id, "w", "cancelled by request")
    # terminal job: cancel is a no-op
    assert queue.cancel(j.id).status is JobStatus.FAILED


def test_cancel_requested_job_not_resurrected_after_crash(
    queue: PostgresJobQueue, engine: Engine
) -> None:
    queue.enqueue("noop")
    j = queue.claim("w", 60)
    assert j is not None
    queue.cancel(j.id)
    expire_lease(engine, j.id)
    assert queue.requeue_expired() == 1
    assert queue.get(j.id).status is JobStatus.CANCELLED


def test_concurrent_recovery_is_safe(engine: Engine) -> None:
    q = PostgresJobQueue(engine, max_queued_jobs=100, default_max_attempts=3)
    for _ in range(20):
        q.enqueue("noop")
    for i in range(20):
        j = q.claim(f"dead{i}", 60)
        assert j is not None
        expire_lease(engine, j.id)
    with ThreadPoolExecutor(8) as ex:
        touched = sum(ex.map(lambda _: q.requeue_expired(), range(8)))
    assert touched == 20  # each expired job recovered exactly once
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM job WHERE status='queued'")).scalar_one() == 20
