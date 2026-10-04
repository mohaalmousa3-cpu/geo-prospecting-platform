from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import Engine, text

from geo_common.queue import JobStatus
from geo_common.queue_pg import PostgresJobQueue
from runner.handlers import DEFAULT_HANDLERS, noop
from runner.loop import Runner

pytestmark = pytest.mark.integration

H = {
    **DEFAULT_HANDLERS,
    "sleep": "handlers_for_tests:sleeper",
    "boom": "handlers_for_tests:boom",
    "insufficient": "handlers_for_tests:insufficient",
    "crash": "handlers_for_tests:hard_crash",
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


def test_handler_exception_fails_job_with_message(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("boom")
    make_runner(queue).run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "handler exploded" in (f.error or "")
    assert f.attempts == 1  # handler errors are not retried


def test_insufficient_data_is_a_normal_terminal_state(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("insufficient")
    make_runner(queue).run_once()
    d = queue.get(j.id)
    assert d.status is JobStatus.INSUFFICIENT_DATA and d.error == "no usable scenes"


def test_unknown_job_type_fails(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("does-not-exist")
    make_runner(queue).run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "no handler" in (f.error or "")


def test_timeout_kills_child_and_fails(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("sleep", {"s": 30})
    t0 = time.monotonic()
    make_runner(queue, job_timeout=1.0).run_once()
    assert time.monotonic() - t0 < 10
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and "timeout" in (f.error or "")


def test_hard_crash_is_retried_then_failed(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("crash", max_attempts=2)
    r = make_runner(queue)
    r.run_once()
    assert queue.get(j.id).status is JobStatus.QUEUED  # attempt 1 died → retry
    r.run_once()
    f = queue.get(j.id)
    assert f.status is JobStatus.FAILED and f.attempts == 2 and "died" in (f.error or "")


def test_cancel_while_running_is_honoured(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("sleep", {"s": 30})
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


def test_lease_is_renewed_for_long_jobs(queue: PostgresJobQueue, engine: Engine) -> None:
    """Job outlives its 1s lease; heartbeats must keep it ours, and a rival sweep must not steal it."""
    j = queue.enqueue("sleep", {"s": 2.5})
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


def test_lease_loss_abandons_without_overwriting(queue: PostgresJobQueue, engine: Engine) -> None:
    """If another actor takes the job over, the old worker must stop and not write a result."""
    j = queue.enqueue("sleep", {"s": 30})
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


def test_graceful_stop_returns_running_job_to_queue(queue: PostgresJobQueue) -> None:
    j = queue.enqueue("sleep", {"s": 30})
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
