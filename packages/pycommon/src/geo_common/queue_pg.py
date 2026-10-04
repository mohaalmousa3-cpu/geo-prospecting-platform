"""PostgreSQL-backed JobQueue using FOR UPDATE SKIP LOCKED (ADR-0007)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from geo_common.queue import (
    Heartbeat,
    JobNotFoundError,
    JobQueue,
    JobRecord,
    JobStatus,
    QueueFullError,
)

_COLS = (
    "id, type, status, priority, payload, attempts, max_attempts, locked_by, "
    "lease_expires_at, cancel_requested, error, created_at, started_at, finished_at"
)
_MAX_ERROR_CHARS = 2000
_ENQUEUE_LOCK_KEY = 7_000_001  # advisory lock serialising enqueue count+insert


def _record(row: Any) -> JobRecord:
    m = row._mapping
    return JobRecord(
        id=m["id"],
        type=m["type"],
        status=JobStatus(m["status"]),
        priority=m["priority"],
        payload=m["payload"],
        attempts=m["attempts"],
        max_attempts=m["max_attempts"],
        locked_by=m["locked_by"],
        lease_expires_at=m["lease_expires_at"],
        cancel_requested=m["cancel_requested"],
        error=m["error"],
        created_at=m["created_at"],
        started_at=m["started_at"],
        finished_at=m["finished_at"],
    )


def _trim(msg: str | None) -> str | None:
    return None if msg is None else msg[:_MAX_ERROR_CHARS]


class PostgresJobQueue(JobQueue):
    def __init__(self, engine: Engine, *, max_queued_jobs: int, default_max_attempts: int) -> None:
        self._engine = engine
        self._max_queued = max_queued_jobs
        self._default_attempts = default_max_attempts

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: int = 0,
        max_attempts: int | None = None,
    ) -> JobRecord:
        with self._engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ENQUEUE_LOCK_KEY})
            queued = conn.execute(text("SELECT count(*) FROM job WHERE status='queued'")).scalar_one()
            if queued >= self._max_queued:
                raise QueueFullError(self._max_queued)
            row = conn.execute(
                text(
                    f"INSERT INTO job (type, priority, payload, max_attempts) "
                    f"VALUES (:t, :p, CAST(:pl AS jsonb), :m) RETURNING {_COLS}"
                ),
                {
                    "t": job_type,
                    "p": priority,
                    "pl": json.dumps(payload or {}),
                    "m": max_attempts or self._default_attempts,
                },
            ).one()
        return _record(row)

    def get(self, job_id: UUID) -> JobRecord:
        with self._engine.connect() as conn:
            row = conn.execute(text(f"SELECT {_COLS} FROM job WHERE id=:i"), {"i": job_id}).first()
        if row is None:
            raise JobNotFoundError(str(job_id))
        return _record(row)

    def claim(self, worker_id: str, lease_seconds: int) -> JobRecord | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    UPDATE job SET status='running', locked_by=:w,
                        lease_expires_at = now() + make_interval(secs => :lease),
                        attempts = attempts + 1, started_at = now(), error = NULL
                    WHERE id = (
                        SELECT id FROM job
                        WHERE status='queued' AND NOT cancel_requested
                        ORDER BY priority DESC, created_at
                        FOR UPDATE SKIP LOCKED LIMIT 1)
                    RETURNING {_COLS}
                    """
                ),
                {"w": worker_id, "lease": lease_seconds},
            ).first()
        return None if row is None else _record(row)

    def heartbeat(self, job_id: UUID, worker_id: str, lease_seconds: int) -> Heartbeat:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE job SET lease_expires_at = now() + make_interval(secs => :lease)
                    WHERE id=:i AND locked_by=:w AND status='running'
                    RETURNING cancel_requested
                    """
                ),
                {"i": job_id, "w": worker_id, "lease": lease_seconds},
            ).first()
        if row is None:
            return Heartbeat(owned=False)
        return Heartbeat(owned=True, cancel_requested=row[0])

    def complete(
        self,
        job_id: UUID,
        worker_id: str,
        status: JobStatus = JobStatus.SUCCEEDED,
        message: str | None = None,
    ) -> bool:
        if status not in (JobStatus.SUCCEEDED, JobStatus.INSUFFICIENT_DATA, JobStatus.CANCELLED):
            raise ValueError("complete() accepts only SUCCEEDED, INSUFFICIENT_DATA or CANCELLED")
        return self._finish(job_id, worker_id, status, _trim(message))

    def fail(self, job_id: UUID, worker_id: str, error: str, *, retryable: bool = False) -> bool:
        if not retryable:
            return self._finish(job_id, worker_id, JobStatus.FAILED, _trim(error))
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE job SET
                        status = CASE WHEN cancel_requested THEN 'cancelled'
                                      WHEN attempts < max_attempts THEN 'queued'
                                      ELSE 'failed' END,
                        locked_by = NULL, lease_expires_at = NULL, error = :e,
                        finished_at = CASE WHEN cancel_requested OR attempts >= max_attempts
                                           THEN now() END
                    WHERE id=:i AND locked_by=:w AND status='running' RETURNING id
                    """
                ),
                {"i": job_id, "w": worker_id, "e": _trim(error)},
            ).first()
        return row is not None

    def _finish(self, job_id: UUID, worker_id: str, status: JobStatus, msg: str | None) -> bool:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE job SET status=:s, error=:e, finished_at=now(),
                        locked_by=NULL, lease_expires_at=NULL
                    WHERE id=:i AND locked_by=:w AND status='running' RETURNING id
                    """
                ),
                {"s": status.value, "e": msg, "i": job_id, "w": worker_id},
            ).first()
        return row is not None

    def cancel(self, job_id: UUID) -> JobRecord:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE job SET
                        status = CASE WHEN status='queued' THEN 'cancelled' ELSE status END,
                        finished_at = CASE WHEN status='queued' THEN now() ELSE finished_at END,
                        cancel_requested = true
                    WHERE id=:i AND status IN ('queued','running')
                    """
                ),
                {"i": job_id},
            )
        return self.get(job_id)

    def requeue_expired(self) -> int:
        with self._engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    UPDATE job SET
                        status = CASE WHEN cancel_requested THEN 'cancelled'
                                      WHEN attempts < max_attempts THEN 'queued'
                                      ELSE 'failed' END,
                        error = CASE WHEN cancel_requested OR attempts < max_attempts THEN error
                                     ELSE 'lease expired; max attempts exhausted' END,
                        finished_at = CASE WHEN cancel_requested OR attempts >= max_attempts
                                           THEN now() END,
                        locked_by = NULL, lease_expires_at = NULL
                    WHERE id IN (
                        SELECT id FROM job
                        WHERE status='running' AND lease_expires_at < now()
                        FOR UPDATE SKIP LOCKED)
                    RETURNING id
                    """
                )
            ).all()
        return len(rows)
