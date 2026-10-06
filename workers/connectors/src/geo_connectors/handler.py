"""`catalog_search` job handler (Phase 3a: fixtures only).

Orchestration of one job, outside the pure connector contract: read the AOI, run the connector inside the
fetch window (no database or storage I/O there), then — outside it — write the file and publish the asset.

Publication protocol (ADR-0014 §8, owner policy of 2026-10-05/06):

1. a cancellation already requested stops the job *before* any file is written;
2. a fresh asset id and key are allocated (keys are never reused); the file is written to a staging file,
   flushed and renamed atomically;
3. one transaction verifies — under the AOI and job locks — that the job is running, belongs to the expected
   AOI/project, is held by this worker and has no cancellation requested, then inserts provenance and asset;
4. only after a successful publication does the handler return, and the runner then completes the job.

If publication is refused or fails, only this worker's own freshly allocated key (and its staging file) is
removed, with a bounded number of attempts; anything that cannot be removed stays for the report-only
reconciliation. A cancellation recorded after a successful publication leaves the asset linked to the
cancelled job (deliberate lifecycle rule); AOI/project deletion still removes it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from geo_common.assets_pg import (
    AssetBusyError,
    PublishHooks,
    PublishRefusedError,
    cleanup_own_files,
    load_job_target,
    publish_asset,
)
from geo_common.config import Settings, get_settings
from geo_common.db import make_engine
from geo_common.storage import LocalStorage, StorageBackend
from geo_connectors.contracts import FetchContext
from geo_connectors.errors import ConnectorRequestError, PublicationBusyError, PublicationRefusedError
from geo_connectors.registry import ConnectorRegistry, resolve_connector
from geo_connectors.request_hash import request_hash

log = logging.getLogger("geo_connectors.handler")
KIND = "scene_catalog"
MEDIA_TYPE = "application/json"
ASSET_FORMAT = 1


@dataclass(frozen=True)
class HandlerOutcome:
    """Duck-typed result: the runner reads `.status` ("succeeded" | "insufficient_data" | "cancelled") and
    `.message`. Defined here so this package never imports the runner (dependency direction, ADR-0011)."""

    status: str
    message: str | None = None


def _result(status: str, message: str | None = None) -> HandlerOutcome:
    return HandlerOutcome(status, message)


def _parse_payload(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    try:
        start, end = date.fromisoformat(str(payload["start"])), date.fromisoformat(str(payload["end"]))
        collections = tuple(str(c) for c in payload["collections"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConnectorRequestError("payload needs ISO 'start' and 'end' and a 'collections' list") from exc
    max_items = payload.get("max_items", settings.MAX_SCENES_PER_JOB)
    if not isinstance(max_items, int) or isinstance(max_items, bool):
        raise ConnectorRequestError("max_items must be an integer")
    return {
        "start": start,
        "end": end,
        "collections": collections,
        "max_items": min(max_items, settings.MAX_SCENES_PER_JOB),
        "fixture_name": str(payload.get("fixture", "synthetic_catalog_v1")),
    }


def run_catalog_search(
    payload: dict[str, Any],
    context: dict[str, Any],
    *,
    engine: Any,  # a SQLAlchemy Engine (typed Any: this package declares no third-party dependency)
    storage: StorageBackend,
    settings: Settings,
    registry: ConnectorRegistry | None = None,
    hooks: PublishHooks | None = None,
    lock_timeout_ms: int | None = None,
    backoff: Any = None,
) -> HandlerOutcome:
    job_id, worker_id = UUID(context["job_id"]), str(context["worker_id"])
    target = load_job_target(engine, job_id)
    if target is None:
        raise PublicationRefusedError("target_deleted")
    aoi_id, project_id = target.aoi_id, target.project_id
    connector = resolve_connector(
        settings.CONNECTOR_MODE, "fixture", registry
    )  # disabled/live: explicit error
    p = _parse_payload(payload, settings)
    ctx = FetchContext(
        aoi_geojson=json.loads(target.aoi_geojson),
        start=p["start"],
        end=p["end"],
        collections=p["collections"],
        max_items=p["max_items"],
        max_window_days=settings.MAX_TIME_WINDOW_DAYS,
        fixture_name=p["fixture_name"],
    )
    fetched = connector.fetch(ctx)  # pure: no database or storage I/O inside the fetch window
    if not fetched.records:
        return _result("insufficient_data", "no catalogue items matched the request")

    body = json.dumps(
        {
            "asset_format": ASSET_FORMAT,
            "records": [asdict(r) for r in fetched.records],
            "truncated": fetched.truncated,
            "source": asdict(fetched.source),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(body) > settings.MAX_UPLOAD_MB * 1024 * 1024:  # provisional reuse of the upload cap (ADR-0008)
        raise ConnectorRequestError("catalogue asset exceeds the size cap")
    digest = hashlib.sha256(body).hexdigest()
    req_hash = request_hash(KIND, ctx, fetched.source)

    # (1) a cancellation requested before publication stops everything before any file exists
    if target.cancel_requested:
        return _result("cancelled", "cancellation requested before publication")

    asset_id = uuid4()  # (2) fresh id and key per attempt; never reused
    key = f"projects/{project_id}/aois/{aoi_id}/jobs/{job_id}/{asset_id}.json"
    storage.put(key, body)
    kw: dict[str, Any] = {}
    if lock_timeout_ms is not None:
        kw["lock_timeout_ms"] = lock_timeout_ms
    if backoff is not None:
        kw["backoff"] = backoff
    try:
        outcome = publish_asset(  # (3) verified under locks
            engine,
            asset_id=asset_id,
            job_id=job_id,
            worker_id=worker_id,
            aoi_id=aoi_id,
            project_id=project_id,
            kind=KIND,
            storage_key=key,
            media_type=MEDIA_TYPE,
            size_bytes=len(body),
            sha256=digest,
            request_hash=req_hash,
            provenance_record={
                "kind": KIND,
                "job_id": str(job_id),
                "asset_id": str(asset_id),
                "request_hash": req_hash,
                "source": asdict(fetched.source),
            },
            hooks=hooks,
            **kw,
        )
    except PublishRefusedError as exc:
        cleanup_own_files(storage, key)
        if exc.reason == "cancel_requested":
            return _result("cancelled", "cancellation requested before publication")
        raise PublicationRefusedError(exc.reason) from exc
    except AssetBusyError as exc:
        cleanup_own_files(storage, key)
        raise PublicationBusyError(str(exc)) from exc
    except BaseException:
        cleanup_own_files(storage, key)
        raise
    if not outcome.created:  # idempotent retry: the matching asset already exists; drop the duplicate file
        cleanup_own_files(storage, key)
        return _result("succeeded", f"asset {outcome.asset.id} already published for this request")
    return _result("succeeded", f"published asset {outcome.asset.id}")


def catalog_search(payload: dict[str, Any], context: dict[str, Any]) -> HandlerOutcome:
    """Runner entry point (import path `geo_connectors.handler:catalog_search`)."""
    settings = get_settings()
    engine = make_engine(settings.database_url, pool_size=1)
    try:
        return run_catalog_search(
            payload,
            context,
            engine=engine,
            storage=LocalStorage(settings.STORAGE_LOCAL_PATH),
            settings=settings,
        )
    finally:
        engine.dispose()
