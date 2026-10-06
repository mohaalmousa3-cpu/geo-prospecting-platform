"""Jobs API: `noop` (Phase 1) and the fixtures-only `catalog_search` (Phase 3a, ADR-0014).

No endpoint returns a scientific result. `catalog_search` jobs are bound to an AOI; the project is derived
from the AOI by the queue layer and is never accepted from the client.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.catalog_jobs import require_connector_mode, validate_catalog_payload
from app.errors import ApiError
from geo_common.config import Settings
from geo_common.models._generated import Job, JobStatus, JobType
from geo_common.queue import (
    JobNotFoundError,
    JobQueue,
    JobRecord,
    JobTargetNotFoundError,
    QueueBusyError,
    QueueFullError,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

NOOP_MAX_SLEEP_SECONDS = 60.0


class NoopPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sleep_seconds: float = Field(default=0, ge=0, le=NOOP_MAX_SLEEP_SECONDS)


class JobCreate(BaseModel):
    """`project_id` is not a field and `extra="forbid"` rejects it: the project comes from the AOI."""

    model_config = ConfigDict(extra="forbid")
    type: JobType
    aoi_id: UUID | None = Field(
        default=None, description="Required for catalog_search; not allowed for noop."
    )
    payload: dict[str, Any] = Field(default_factory=dict)


def _queue(request: Request) -> JobQueue:
    q: JobQueue = request.app.state.queue
    return q


def _to_model(r: JobRecord) -> Job:
    return Job(
        id=r.id,
        type=JobType(r.type),
        aoi_id=r.aoi_id,
        project_id=r.project_id,
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


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Job,
    summary="Create a job (noop, or a fixtures-only catalog_search)",
)
def create_job(body: JobCreate, request: Request) -> Job:
    if body.type is JobType.catalog_search:
        return _create_catalog_search(body, request)
    if body.aoi_id is not None:
        raise ApiError(422, "validation_error", "noop jobs take no aoi_id")
    try:
        payload = NoopPayload.model_validate(body.payload).model_dump()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) if e["loc"] else "payload" for e in exc.errors())
        raise ApiError(422, "validation_error", f"invalid noop payload: {fields}") from exc
    return _to_model(_enqueue(request, body.type.value, payload))


def _create_catalog_search(body: JobCreate, request: Request) -> Job:
    """Precedence of refusals: 422 (shape, limits) → connector mode (409/501) → 404 (AOI) → 429/503 (queue).

    No refusal creates a job. Nothing here opens a connector, a socket or a file.
    """
    settings: Settings = request.app.state.settings
    if body.aoi_id is None:
        raise ApiError(422, "validation_error", "aoi_id is required for catalog_search jobs")
    payload = validate_catalog_payload(body.payload, settings)
    require_connector_mode(settings)
    try:
        record = _enqueue(request, body.type.value, payload, aoi_id=body.aoi_id)
    except JobTargetNotFoundError as exc:
        raise ApiError(404, "aoi_not_found", "AOI not found") from exc
    return _to_model(record)


def _enqueue(request: Request, job_type: str, payload: dict[str, Any], **kw: Any) -> JobRecord:
    try:
        return _queue(request).enqueue(job_type, payload, **kw)
    except QueueFullError as exc:
        raise ApiError(
            429, "queue_full", f"queue is full (MAX_QUEUED_JOBS={exc.limit}); retry later"
        ) from exc
    except QueueBusyError as exc:  # the queue transaction exhausted its attempt budget (lock contention)
        raise ApiError(
            503, "retry_later", "the queue is busy; the job was not created, retry shortly"
        ) from exc


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
