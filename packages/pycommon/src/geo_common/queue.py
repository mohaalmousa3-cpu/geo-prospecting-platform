"""Job queue abstraction (ADR-0007). Engines and the API depend only on this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INSUFFICIENT_DATA = "insufficient_data"

    @property
    def terminal(self) -> bool:
        return self not in (JobStatus.QUEUED, JobStatus.RUNNING)


class QueueFullError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"queue is full: MAX_QUEUED_JOBS={limit}")
        self.limit = limit


class JobNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    type: str
    status: JobStatus
    priority: int
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    locked_by: str | None
    lease_expires_at: datetime | None
    cancel_requested: bool
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class Heartbeat:
    """Result of a lease renewal. `owned=False` means the lease was lost: stop working."""

    owned: bool
    cancel_requested: bool = False


class JobQueue(ABC):
    @abstractmethod
    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: int = 0,
        max_attempts: int | None = None,
    ) -> JobRecord:
        """Insert a queued job. Raises QueueFullError beyond MAX_QUEUED_JOBS."""

    @abstractmethod
    def get(self, job_id: UUID) -> JobRecord:
        """Raises JobNotFoundError."""

    @abstractmethod
    def claim(self, worker_id: str, lease_seconds: int) -> JobRecord | None:
        """Atomically claim the next queued job (higher priority first, then oldest)."""

    @abstractmethod
    def heartbeat(self, job_id: UUID, worker_id: str, lease_seconds: int) -> Heartbeat:
        """Extend the lease if `worker_id` still owns the running job."""

    @abstractmethod
    def complete(
        self,
        job_id: UUID,
        worker_id: str,
        status: JobStatus = JobStatus.SUCCEEDED,
        message: str | None = None,
    ) -> bool:
        """Finish a job as SUCCEEDED, INSUFFICIENT_DATA or CANCELLED. False if the lease was lost."""

    @abstractmethod
    def fail(self, job_id: UUID, worker_id: str, error: str, *, retryable: bool = False) -> bool:
        """Mark failed (or re-queue if retryable and attempts remain). False if lease lost."""

    @abstractmethod
    def cancel(self, job_id: UUID) -> JobRecord:
        """Queued → cancelled now; running → cancel_requested; terminal → unchanged."""

    @abstractmethod
    def requeue_expired(self) -> int:
        """Recover jobs whose lease expired. Returns number of jobs touched."""
