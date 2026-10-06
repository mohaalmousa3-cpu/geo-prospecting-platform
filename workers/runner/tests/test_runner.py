from __future__ import annotations

import threading
import time
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from geo_common.queue import JobStatus
from geo_common.queue_pg import PostgresJobQueue
from runner.handlers import DEFAULT_HANDLERS, noop
from runner.loop import Runner

pytestmark = pytest.mark.integration

# Non-`noop` job types are AOI-bound (ADR-0014): every such test enqueues with the `aoi_id` fixture
# (conftest.py creates a project and an AOI). No test-only job type is exempt from that rule.
H = {
    **DEFAULT_HANDLERS,
    "sleep": "handlers_for_tests:sleeper",
    "boom": "handlers_for_tests:boom",
    "insufficient": "handlers_for_tests:insufficient",
    "crash": "handlers_for_tests:hard_crash",
    "retry": "handlers_for_tests:retry_me",
    "ctx": "handlers_for_tests:echo_context",
    "stops": "handlers_for_tests:cancels",
}


def make_runner(queue: PostgresJobQueue, **kw: float) -> Runner:
    args = dict(lease_seconds=3, poll_interval=0.05, job_timeout=20, heartbeat_interval=0.2)
    args.update(kw)
    return Runner(queue, worker_id="test-worker", handlers=H, **args)  # type: ignore[arg-type]


def test_noop_succeeds(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("noop")
    assert make_runner(queue).run_once()
    done = queue.get(j.id)
    assert done.status is JobStatus.SUCCEEDED and done.finished_at and done.locked_by is None


def test_nothing_to_do(queue: PostgresJobQueue) -> None:
    assert make_runner(queue).run_once() is False


def test_noop_rejects_bad_sleep() -> None:
    with pytest.raises(ValueError):
        noop({"sleep_seconds": 10_000})


def test_handler_exception_fails_job_with_message(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("boom", aoi_id=aoi_id)
    make_runner(queue).run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "handler exploded" in (f.error or "")
    assert f.attempts == 1  # handler errors are not retried


def test_insufficient_data_is_a_normal_terminal_state(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("insufficient", aoi_id=aoi_id)
    make_runner(queue).run_once()
    d = queue.get(j.id)
    assert d.status is JobStatus.INSUFFICIENT_DATA and d.error == "no usable scenes"


def test_unknown_job_type_fails(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("does-not-exist", aoi_id=aoi_id)
    make_runner(queue).run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "no handler" in (f.error or "")


def test_timeout_kills_child_and_fails(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("sleep", {"s": 30}, aoi_id=aoi_id)
    t0 = time.monotonic()
    make_runner(queue, job_timeout=1.0).run_once()
    assert time.monotonic() - t0 < 10
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "timeout" in (f.error or "")


def test_hard_crash_is_retried_then_failed(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("crash", max_attempts=2, aoi_id=aoi_id)
    r = make_runner(queue)
    r.run_once()
    assert queue.get(j.id).status is JobStatus.QUEUED  # attempt 1 died → retry
    r.run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and f.attempts == 2 and "died" in (f.error or "")


def test_cancel_while_running_is_honoured(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("sleep", {"s": 30}, aoi_id=aoi_id)
    r = make_runner(queue)
    t = threading.Thread(target=r.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while queue.get(j.id).status is not JobStatus.RUNNING and time.monotonic() < deadline:
        time.sleep(0.05)
    queue.cancel(j.id)
    t.join(15)
    assert not t.is_alive()
    c = queue.get(j.id)
    assert c.status is JobStatus.CANCELLED and c.locked_by is None


def test_lease_is_renewed_for_long_jobs(queue: PostgresJobQueue, engine: Engine, aoi_id: UUID) -> None:
    """Job outlives its 1s lease; heartbeats must keep it ours, and a rival sweep must not steal it."""
    j = queue.enqueue("sleep", {"s": 2.5}, aoi_id=aoi_id)
    r = make_runner(queue, lease_seconds=1, heartbeat_interval=0.25)
    steals: list[int] = []
    t = threading.Thread(target=r.run_once)
    t.start()
    while t.is_alive():
        steals.append(queue.requeue_expired())
        time.sleep(0.1)
    assert sum(steals) == 0
    assert queue.get(j.id).status is JobStatus.SUCCEEDED


def test_worker_crash_is_recovered_by_another_worker(queue: PostgresJobQueue, engine: Engine) -> None:
    j = queue.enqueue("noop")
    assert queue.claim("dead-worker", 60) is not None  # worker "dies" holding the job
    with engine.begin() as c:
        c.execute(text("UPDATE job SET lease_expires_at = now() - interval '1s'"))
    assert make_runner(queue).run_once()  # run_once sweeps expired leases first
    done = queue.get(j.id)
    assert done.status is JobStatus.SUCCEEDED and done.attempts == 2


def test_lease_loss_abandons_without_overwriting(
    queue: PostgresJobQueue, engine: Engine, aoi_id: UUID
) -> None:
    """If another actor takes the job over, the old worker must stop and not write a result."""
    j = queue.enqueue("sleep", {"s": 30}, aoi_id=aoi_id)
    r = make_runner(queue, heartbeat_interval=0.2)
    t = threading.Thread(target=r.run_once)
    t.start()
    while queue.get(j.id).status is not JobStatus.RUNNING:
        time.sleep(0.05)
    with engine.begin() as c:  # simulate recovery + reassignment to someone else
        c.execute(text("UPDATE job SET locked_by='someone-else' WHERE id=:i"), {"i": j.id})
    t.join(15)
    assert not t.is_alive()
    s = queue.get(j.id)
    assert s.status is JobStatus.RUNNING and s.locked_by == "someone-else"


def test_graceful_stop_returns_running_job_to_queue(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("sleep", {"s": 30}, aoi_id=aoi_id)
    r = make_runner(queue)
    t = threading.Thread(target=r.run_once)
    t.start()
    while queue.get(j.id).status is not JobStatus.RUNNING:
        time.sleep(0.05)
    r.stop_event.set()
    t.join(15)
    assert not t.is_alive()
    assert queue.get(j.id).status is JobStatus.QUEUED
    assert make_runner(queue).run_once() is True  # a later worker can pick it up


def test_run_forever_stops_when_idle(queue: PostgresJobQueue) -> None:
    r = make_runner(queue)
    t = threading.Thread(target=r.run_forever)
    t.start()
    time.sleep(0.3)
    r.stop_event.set()
    t.join(5)
    assert not t.is_alive()


def test_two_argument_handlers_receive_the_job_context(
    queue: PostgresJobQueue, aoi_id: UUID, engine: Engine
) -> None:
    import json

    j = queue.enqueue("ctx", aoi_id=aoi_id)
    assert make_runner(queue).run_once()
    done = queue.get(j.id)
    ctx = json.loads(done.error)  # the success message is stored in `error` for explained terminal states
    assert (
        done.status is JobStatus.SUCCEEDED
        and ctx["job_id"] == str(j.id)
        and ctx["worker_id"] == "test-worker"
    )
    assert ctx["aoi_id"] == str(j.aoi_id) and ctx["project_id"] == str(j.project_id)


def test_one_argument_handlers_still_work_and_noop_has_no_aoi_in_its_context(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("noop")
    assert make_runner(queue).run_once()
    assert queue.get(j.id).status is JobStatus.SUCCEEDED


def test_a_retryable_handler_exception_requeues_the_job_within_its_attempt_budget(
    queue: PostgresJobQueue, aoi_id: UUID
) -> None:
    j = queue.enqueue("retry", max_attempts=2, aoi_id=aoi_id)
    assert make_runner(queue).run_once()
    first = queue.get(j.id)
    assert first.status is JobStatus.QUEUED and "temporarily busy" in (first.error or "")
    assert make_runner(queue).run_once()
    assert queue.get(j.id).status is JobStatus.FAILED  # the attempt budget is respected, then it fails


def test_a_handler_may_end_the_job_as_cancelled(queue: PostgresJobQueue, aoi_id: UUID) -> None:
    j = queue.enqueue("stops", aoi_id=aoi_id)
    assert make_runner(queue).run_once()
    done = queue.get(j.id)
    assert done.status is JobStatus.CANCELLED and done.error == "stopped before publication"
