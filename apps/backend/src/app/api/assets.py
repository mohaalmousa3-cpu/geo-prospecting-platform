"""Asset endpoints (Phase 3a): list, get, content, delete. Assets are staged inputs, never results.

There is deliberately no creation endpoint: assets are published by the worker (ADR-0014 §8). Nothing here
carries a confidence, score or interpretation.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import get_storage
from app.errors import ApiError
from geo_common.assets_pg import (
    AssetBusyError,
    AssetJobActiveError,
    AssetNotFoundError,
    AssetRecord,
    delete_asset,
    drain_tombstones,
    get_asset,
    list_assets,
    tombstone_pending,
)
from geo_common.models._generated import Asset, AssetDeleted, AssetList

router = APIRouter(prefix="/assets", tags=["assets"])
log = logging.getLogger("app.assets")


def to_model(a: AssetRecord) -> Asset:
    return Asset.model_validate(
        {
            "id": a.id,
            "project_id": a.project_id,
            "aoi_id": a.aoi_id,
            "job_id": a.job_id,
            "kind": a.kind,
            "media_type": a.media_type,
            "size_bytes": a.size_bytes,
            "sha256": a.sha256,
            "created_at": a.created_at,
            "provenance": a.provenance,
        }
    )


@router.get("", response_model=AssetList, summary="List staged assets (oldest first)")
def list_(
    request: Request,
    project_id: UUID | None = None,
    aoi_id: UUID | None = None,
    job_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssetList:
    items, total = list_assets(
        request.app.state.engine,
        project_id=project_id,
        aoi_id=aoi_id,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )
    return AssetList.model_validate({"items": [to_model(a).model_dump() for a in items], "total": total})


@router.get("/{asset_id}", response_model=Asset, summary="Get one staged asset")
def get(asset_id: UUID, request: Request) -> Asset:
    a = get_asset(request.app.state.engine, asset_id)
    if a is None:
        raise ApiError(404, "asset_not_found", "asset not found")
    return to_model(a)


@router.get("/{asset_id}/content", summary="Download the stored file of an asset")
def content(asset_id: UUID, request: Request) -> Response:
    a = get_asset(request.app.state.engine, asset_id)
    if a is None:
        raise ApiError(404, "asset_not_found", "asset not found")
    storage = get_storage(request)
    try:
        data = storage.get(a.storage_key)
    except FileNotFoundError as exc:
        raise ApiError(404, "asset_file_missing", "the asset row exists but its file is missing") from exc
    return Response(
        content=data,
        media_type=a.media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{a.id}.json"',
            "ETag": f'"{a.sha256}"',
        },
    )


@router.delete("/{asset_id}", response_model=AssetDeleted, summary="Delete one staged asset")
def delete(asset_id: UUID, request: Request) -> AssetDeleted:
    engine = request.app.state.engine
    try:
        key = delete_asset(engine, asset_id)
    except AssetNotFoundError as exc:
        raise ApiError(404, "asset_not_found", "asset not found") from exc
    except AssetJobActiveError as exc:
        raise ApiError(
            409, "has_active_jobs", "the asset belongs to a queued or running job; cancel it first"
        ) from exc
    except AssetBusyError as exc:
        raise ApiError(503, "retry_later", "the operation could not complete; retry shortly") from exc
    pending = True  # the row deletion is committed: cleanup trouble below never turns this into a failure
    try:
        drain_tombstones(engine, get_storage(request))
        pending = tombstone_pending(engine, key)
    except Exception:
        log.exception("post-commit cleanup after asset deletion failed; the file stays pending")
    return AssetDeleted.model_validate({"deleted": True, "files_pending_cleanup": 1 if pending else 0})
