"""AOI endpoints. Geometry and bookkeeping only: no analysis, no scores, no results."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status
from pydantic import Field

from app import deletion
from app.aoi.errors import AoiValidationError
from app.aoi.repository import AoiLimitReachedError, AoiRepository
from app.aoi.service import (
    AoiRequest,
    Draft,
    draft_from_request,
    draft_from_upload,
    limits_view,
)
from app.errors import ApiError, translate_deletion_error
from app.projects import ProjectNotFoundError
from geo_common.config import Settings
from geo_common.models._generated import Aoi, AoiDraft, AoiLimits, AoiList

router = APIRouter(prefix="/aois", tags=["aois"])

RequestBody = Annotated[AoiRequest, Field(discriminator="method")]


def _settings(request: Request) -> Settings:
    s: Settings = request.app.state.settings
    return s


def _repo(request: Request) -> AoiRepository:
    return AoiRepository(request.app.state.engine, _settings(request).MAX_STORED_AOIS)


def _wrap(fn: Any, *a: Any) -> Draft:
    try:
        return fn(*a)  # type: ignore[no-any-return]
    except AoiValidationError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from exc


def _save(request: Request, draft: Draft, name: str | None, project_id: UUID | None) -> Aoi:
    if project_id is None:
        raise ApiError(422, "project_required", "project_id is required to save an AOI")
    if not name or not name.strip():
        raise ApiError(422, "name_required", "an AOI name is required to save")
    if len(name) > 120:
        raise ApiError(422, "name_too_long", "AOI name must be at most 120 characters")
    try:
        row = _repo(request).create(project_id, name.strip(), draft)
    except ProjectNotFoundError as exc:
        raise ApiError(404, "project_not_found", "project not found") from exc
    except AoiLimitReachedError as exc:
        raise ApiError(409, "aoi_limit_reached", str(exc)) from exc
    return Aoi.model_validate(row)


@router.get("/limits", response_model=AoiLimits, summary="Provisional AOI limits (ADR-0008)")
def limits(request: Request) -> AoiLimits:
    return limits_view(_settings(request))


@router.post("/preview", response_model=AoiDraft, summary="Validate and normalise an AOI without saving")
def preview(body: RequestBody, request: Request) -> AoiDraft:
    return AoiDraft.model_validate(_wrap(draft_from_request, body, _settings(request)).as_dict())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Aoi, summary="Create an AOI")
def create(body: RequestBody, request: Request) -> Aoi:
    draft = _wrap(draft_from_request, body, _settings(request))
    return _save(request, draft, draft.name, body.project_id)


@router.post("/upload", response_model=None, summary="Create (or preview) an AOI from an uploaded file")
async def upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    project_id: Annotated[UUID | None, Form()] = None,
    preview: Annotated[bool, Query()] = False,
) -> Any:
    s = _settings(request)
    max_bytes = s.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApiError(413, "payload_too_large", f"file exceeds MAX_UPLOAD_MB={s.MAX_UPLOAD_MB}")
    if not data:
        raise ApiError(422, "empty_file", "uploaded file is empty")
    draft = _wrap(draft_from_upload, file.filename or "upload", data, s, name)
    if preview:
        return AoiDraft.model_validate(draft.as_dict())
    return Response(
        content=_save(request, draft, draft.name, project_id).model_dump_json(),
        media_type="application/json",
        status_code=201,
    )


@router.get("", response_model=AoiList, summary="List saved AOIs (newest first)")
def list_aois(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    project_id: Annotated[UUID | None, Query()] = None,
) -> AoiList:
    items, total = _repo(request).list(limit, offset, project_id)
    return AoiList.model_validate({"items": items, "total": total})


@router.get("/{aoi_id}", response_model=Aoi, summary="Get an AOI with geometry")
def get_aoi(aoi_id: UUID, request: Request) -> Aoi:
    row = _repo(request).get(aoi_id)
    if row is None:
        raise ApiError(404, "aoi_not_found", "AOI not found")
    return Aoi.model_validate(row)


@router.delete("/{aoi_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an AOI")
def delete_aoi(
    aoi_id: UUID,
    request: Request,
    delete_dependents: Annotated[
        bool, Query(description="Also delete the AOI's finished jobs (queued/running jobs always refuse)")
    ] = False,
) -> Response:
    try:
        found = _repo(request).delete(aoi_id, cascade=delete_dependents)
    except (
        deletion.HasActiveJobsError,
        deletion.NeedsCascadeError,
        deletion.StillReferencedError,
        deletion.RetryLaterError,
        deletion.IntegrityFailureError,
    ) as exc:
        raise translate_deletion_error(exc) or exc from exc
    if not found:
        raise ApiError(404, "aoi_not_found", "AOI not found")
    return Response(status_code=204)
