"""Worker loop: claim → run handler in a child process → heartbeat → enforce timeout.

The child process makes the hard timeout enforceable (we can kill it) and keeps a crashing or
leaking handler from taking the worker down.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from multiprocessing.connection import Connection
from typing import Any
from uuid import UUID

from geo_common.queue import JobQueue, JobRecord, JobStatus
from runner.handlers import DEFAULT_HANDLERS, load_handler

log = logging.getLogger("runner")
_CTX = mp.get_context("spawn")


def _child(conn: Connection, handler_path: str, payload: dict[str, Any]) -> None:
    try:
        result = load_handler(handler_path)(payload)
        conn.send(("ok", result.status, result.message))
    except BaseException as exc:  # report everything; parent decides
        conn.send(("error", f"{type(exc).__name__}: {exc}", None))
    finally:
        conn.close()


class Runner:
    def __init__(
        self,
        queue: JobQueue,
        *,
        worker_id: str,
        lease_seconds: int,
        poll_interval: float,
        job_timeout: float,
        handlers: dict[str, str] | None = None,
        heartbeat_interval: float | None = None,
    ) -> None:
        self._q = queue
        self._worker = worker_id
        self._lease = lease_seconds
        self._poll = poll_interval
        self._timeout = job_timeout
        self._handlers = handlers if handlers is not None else DEFAULT_HANDLERS
        self._hb = heartbeat_interval or max(lease_seconds / 3, 0.05)
        self.stop_event = threading.Event()

    # ------------------------------------------------------------------ public
    def run_forever(self) -> None:
        log.info("worker started", extra={"worker_id": self._worker})
        while not self.stop_event.is_set():
            if not self.run_once():
                self.stop_event.wait(self._poll)
        log.info("worker stopped", extra={"worker_id": self._worker})

    def run_once(self) -> bool:
        """Recover expired leases, claim one job, process it. True if a job was processed."""
        self._q.requeue_expired()
        job = self._q.claim(self._worker, self._lease)
        if job is None:
            return False
        self._process(job)
        return True

    # ----------------------------------------------------------------- private
    def _process(self, job: JobRecord) -> None:
        extra = {"job_id": str(job.id), "worker_id": self._worker}
        handler_path = self._handlers.get(job.type)
        if handler_path is None:
            self._q.fail(job.id, self._worker, f"no handler registered for job type '{job.type}'")
            log.error("no handler for job type", extra=extra)
            return
        log.info("job started (attempt %d)", job.attempts, extra=extra)
        parent, child_conn = _CTX.Pipe(duplex=False)
        proc = _CTX.Process(target=_child, args=(child_conn, handler_path, job.payload), daemon=True)
        proc.start()
        child_conn.close()
        try:
            self._supervise(job.id, proc, parent, extra)
        finally:
            if proc.is_alive():
                proc.kill()
            proc.join(5)
            parent.close()

    def _kill(self, proc: Any) -> None:
        proc.kill()
        proc.join(5)

    def _supervise(self, job_id: UUID, proc: Any, conn: Connection, extra: dict[str, str]) -> None:
        started = last_hb = time.monotonic()
        while True:
            if conn.poll(min(self._hb, 0.2)):
                self._finish_from_child(job_id, proc, conn, extra)
                return
            if not proc.is_alive():
                if conn.poll(0.2):  # result may have landed just before exit
                    self._finish_from_child(job_id, proc, conn, extra)
                else:
                    msg = f"handler process died (exit code {proc.exitcode})"
                    log.error(msg, extra=extra)
                    self._q.fail(job_id, self._worker, msg, retryable=True)
                return
            if self.stop_event.is_set():
                self._kill(proc)
                log.warning("shutdown during job; returning it to the queue", extra=extra)
                self._q.fail(job_id, self._worker, "worker shutdown", retryable=True)
                return
            if time.monotonic() - started > self._timeout:
                self._kill(proc)
                log.error("job timed out", extra=extra)
                self._q.fail(job_id, self._worker, f"timeout after {self._timeout:g}s")
                return
            if time.monotonic() - last_hb >= self._hb:
                last_hb = time.monotonic()
                hb = self._q.heartbeat(job_id, self._worker, self._lease)
                if not hb.owned:
                    self._kill(proc)
                    log.error("lease lost; abandoning job", extra=extra)
                    return
                if hb.cancel_requested:
                    self._kill(proc)
                    log.info("job cancelled while running", extra=extra)
                    self._q.complete(job_id, self._worker, JobStatus.CANCELLED, "cancelled by request")
                    return

    def _finish_from_child(self, job_id: UUID, proc: Any, conn: Connection, extra: dict[str, str]) -> None:
        try:
            kind, a, b = conn.recv()
        except EOFError:
            proc.join(5)
            self._q.fail(
                job_id,
                self._worker,
                f"handler process died (exit code {proc.exitcode})",
                retryable=True,
            )
            return
        if kind == "ok":
            self._q.complete(job_id, self._worker, JobStatus(a), b)
            log.info("job finished: %s", a, extra=extra)
        else:
            log.error("job failed: %s", a, extra=extra)
            self._q.fail(job_id, self._worker, a)
