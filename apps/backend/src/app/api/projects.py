"""Project endpoints (Phase 2.5). Bookkeeping only: no analysis, no results."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.errors import ApiError
from app.projects import (
    ProjectLimitReachedError,
    ProjectNotEmptyError,
    ProjectNotFoundError,
    ProjectRepository,
)
from geo_common.config import Settings
from geo_common.models._generated import Project, ProjectCreateRequest, ProjectList

router = APIRouter(prefix="/projects", tags=["projects"])


def _repo(request: Request) -> ProjectRepository:
    s: Settings = request.app.state.settings
    return ProjectRepository(request.app.state.engine, s.MAX_PROJECTS)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Project, summary="Create a project")
def create(body: ProjectCreateRequest, request: Request) -> Project:
    name = body.name.root.strip()
    if not name:
        raise ApiError(422, "name_required", "project name must not be blank")
    desc = body.description.strip() if body.description else None
    try:
        return Project.model_validate(_repo(request).create(name, desc or None))
    except ProjectLimitReachedError as exc:
        raise ApiError(409, "project_limit_reached", str(exc)) from exc


@router.get("", response_model=ProjectList, summary="List projects (oldest first)")
def list_projects(request: Request) -> ProjectList:
    items, total = _repo(request).list()
    return ProjectList.model_validate({"items": items, "total": total})


@router.get("/{project_id}", response_model=Project, summary="Get a project")
def get_project(project_id: UUID, request: Request) -> Project:
    row = _repo(request).get(project_id)
    if row is None:
        raise ApiError(404, "project_not_found", "project not found")
    return Project.model_validate(row)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a project")
def delete_project(
    project_id: UUID,
    request: Request,
    delete_aois: Annotated[bool, Query(description="Also delete the project's AOIs")] = False,
) -> Response:
    try:
        _repo(request).delete(project_id, delete_aois=delete_aois)
    except ProjectNotFoundError as exc:
        raise ApiError(404, "project_not_found", "project not found") from exc
    except ProjectNotEmptyError as exc:
        raise ApiError(
            409,
            "project_not_empty",
            f"project contains {exc.aoi_count} AOI(s); delete them first or pass delete_aois=true",
        ) from exc
    return Response(status_code=204)
