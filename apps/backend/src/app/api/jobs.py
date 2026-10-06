"""Jobs API. Phase 1 supports only the `noop` job; no endpoint returns a scientific result."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.errors import ApiError
from geo_common.models._generated import Job, JobStatus, JobType
from geo_common.queue import JobNotFoundError, JobQueue, JobRecord, QueueBusyError, QueueFullError

router = APIRouter(prefix="/jobs", tags=["jobs"])

NOOP_MAX_SLEEP_SECONDS = 60.0


class NoopPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sleep_seconds: float = Field(default=0, ge=0, le=NOOP_MAX_SLEEP_SECONDS)


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


def _queue(request: Request) -> JobQueue:
    q: JobQueue = request.app.state.queue
    return q


def _to_model(r: JobRecord) -> Job:
    return Job(
        id=r.id,
        type=JobType(r.type),
        status=JobStatus(r.status.value),
        priority=r.priority,
        attempts=r.attempts,
        max_attempts=r.max_attempts,
        cancel_requested=r.cancel_requested,
        error=r.error,
        created_at=r.created_at,
        started_at=r.started_at,
        finished_at=r.finished_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Job, summary="Create a noop job")
def create_job(body: JobCreate, request: Request) -> Job:
    try:
        payload = NoopPayload.model_validate(body.payload).model_dump()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) if e["loc"] else "payload" for e in exc.errors())
        raise ApiError(422, "validation_error", f"invalid noop payload: {fields}") from exc
    try:
        record = _queue(request).enqueue(body.type.value, payload)
    except QueueFullError as exc:
        raise ApiError(
            429, "queue_full", f"queue is full (MAX_QUEUED_JOBS={exc.limit}); retry later"
        ) from exc
    except QueueBusyError as exc:  # the queue transaction exhausted its attempt budget (lock contention)
        raise ApiError(
            503, "retry_later", "the queue is busy; the job was not created, retry shortly"
        ) from exc
    return _to_model(record)


@router.get("/{job_id}", response_model=Job, summary="Get job status")
def get_job(job_id: UUID, request: Request) -> Job:
    try:
        return _to_model(_queue(request).get(job_id))
    except JobNotFoundError as exc:
        raise ApiError(404, "job_not_found", "job not found") from exc


@router.post("/{job_id}/cancel", response_model=Job, summary="Request cancellation")
def cancel_job(job_id: UUID, request: Request) -> Job:
    try:
        return _to_model(_queue(request).cancel(job_id))
    except JobNotFoundError as exc:
        raise ApiError(404, "job_not_found", "job not found") from exc
