"""Persistence and storage-protocol operations for staged data assets (ADR-0014 §7–§8).

Scope (owner decision 2026-10-06): shared database/repository operations and storage-protocol
helpers *only*. No scientific interpretation, provider policy, network logic, UI behaviour or
orchestration decisions: *when* to publish, *when* to clean up and what a job's outcome is belong to
the worker (`geo_connectors.handler`) and the backend. Assets are inputs, never results: no
confidence, score or interpretation exists here.

Lock order (ADR-0014 §7.5, level by level): project → AOI → job → asset → provenance. The
publication transaction takes the AOI row (`FOR KEY SHARE`) and then the job row (`FOR SHARE`), i.e.
*the same order as the deleters*, instead of relying on the (unspecified) order in which PostgreSQL
fires the two foreign-key checks.
"""

# ruff: noqa: S608  (f-strings interpolate only module constants; all values are bound)

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.storage import LocalStorage, StorageBackend
from geo_common.transactions import (
    DEFAULT_LOCK_TIMEOUT_MS,
    RetryBudgetExhaustedError,
    constraint_name,
    run_transaction,
    sqlstate,
)

log = logging.getLogger("geo_common.assets")

REQUEST_CONSTRAINT = "data_asset_job_request_key"
CLEANUP_ATTEMPTS = 3  # bounded cleanup of a worker's own files
DRAIN_BATCH = 50
STALE_STAGING_SECONDS = 24 * 3600  # reporting threshold only; nothing is ever deleted by age

_COLS = (
    "a.id, a.project_id, a.aoi_id, a.job_id, a.kind, a.media_type, a.size_bytes, a.sha256, "
    "a.request_hash, "
    "a.storage_key, a.provenance_id, a.created_at, p.record AS provenance"
)
_FROM = "FROM data_asset a JOIN provenance p ON p.id = a.provenance_id"


@dataclass(frozen=True)
class AssetRecord:
    id: UUID
    project_id: UUID
    aoi_id: UUID
    job_id: UUID | None
    kind: str
    media_type: str
    size_bytes: int
    sha256: str
    request_hash: str
    storage_key: str
    provenance_id: UUID
    created_at: datetime
    provenance: dict[str, Any] = field(default_factory=dict)


class AssetNotFoundError(Exception):
    pass


class AssetJobActiveError(Exception):
    """The asset belongs to a queued/running job: deletion is refused (has_active_jobs)."""


class AssetBusyError(Exception):
    """The transaction could not complete within its attempt budget (lock contention)."""


class PublishRefusedError(Exception):
    """The publication transaction found the job/target not publishable. `reason` is one of
    target_deleted, target_mismatch, not_running, wrong_owner, cancel_requested."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"asset publication refused: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class PublishResult:
    asset: AssetRecord
    created: (
        bool  # False: an asset for the same (job, kind, request_hash) already existed (idempotent success)
    )


@dataclass
class PublishHooks:
    """Test seam (never set in production): callbacks inside the publication transaction."""

    after_locks: Callable[[Connection], None] | None = None  # AOI and job locks held, nothing inserted yet
    after_insert: Callable[[Connection], None] | None = None  # rows inserted, not yet committed


def _record(row: Any) -> AssetRecord:
    m = row._mapping
    return AssetRecord(**{k: m[k] for k in AssetRecord.__dataclass_fields__})


def _retry_kw(backoff: Callable[[int], None] | None) -> dict[str, Any]:
    return {} if backoff is None else {"backoff": backoff}


# ------------------------------------------------------------------------------------------ publication
def publish_asset(
    engine: Engine,
    *,
    asset_id: UUID,
    job_id: UUID,
    worker_id: str,
    aoi_id: UUID,
    project_id: UUID,
    kind: str,
    storage_key: str,
    media_type: str,
    size_bytes: int,
    sha256: str,
    request_hash: str,
    provenance_record: dict[str, Any],
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    backoff: Callable[[int], None] | None = None,
    hooks: PublishHooks | None = None,
) -> PublishResult:
    """Publish one asset for a running job, verifying under locks that it may be published.

    While holding the AOI (key-share) and job (share) locks it verifies that the job exists, belongs to the
    expected AOI/project, is `running`, is held by `worker_id` and has no cancellation requested. A
    matching
    asset (same job, kind and request hash) is an idempotent success. The caller has already written the file
    (storage-protocol step 2) and owns cleanup when this raises (never this function).
    """

    def op(conn: Connection) -> PublishResult:
        if (
            conn.execute(
                text("SELECT 1 FROM aoi WHERE id = :a AND project_id = :p FOR KEY SHARE"),
                {"a": aoi_id, "p": project_id},
            ).first()
            is None
        ):
            exists = conn.execute(text("SELECT 1 FROM aoi WHERE id = :a"), {"a": aoi_id}).first()
            raise PublishRefusedError("target_mismatch" if exists else "target_deleted")
        job = conn.execute(
            text(
                "SELECT status, locked_by, cancel_requested, aoi_id, project_id FROM job WHERE id = :j "
                "FOR SHARE"
            ),
            {"j": job_id},
        ).first()
        if job is None:
            raise PublishRefusedError("target_deleted")
        if (job.aoi_id, job.project_id) != (aoi_id, project_id):
            raise PublishRefusedError("target_mismatch")
        if job.status != "running":
            raise PublishRefusedError("not_running")
        if job.locked_by != worker_id:
            raise PublishRefusedError("wrong_owner")
        if job.cancel_requested:
            raise PublishRefusedError("cancel_requested")
        if hooks is not None and hooks.after_locks is not None:
            hooks.after_locks(conn)
        existing = conn.execute(
            text(f"SELECT {_COLS} {_FROM} WHERE a.job_id = :j AND a.kind = :k AND a.request_hash = :h"),
            {"j": job_id, "k": kind, "h": request_hash},
        ).first()
        if existing is not None:
            return PublishResult(_record(existing), created=False)
        prov_id = conn.execute(
            text("INSERT INTO provenance (job_id, record) VALUES (:j, CAST(:r AS jsonb)) RETURNING id"),
            {"j": job_id, "r": json.dumps(provenance_record, sort_keys=True)},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO data_asset (id, project_id, aoi_id, job_id, kind, storage_key, "
                "media_type, "
                "size_bytes, sha256, request_hash, provenance_id) VALUES "
                "(:id, :p, :a, :j, :k, :sk, :mt, :sz, :sha, :h, :pid)"
            ),
            {
                "id": asset_id, "p": project_id, "a": aoi_id, "j": job_id, "k": kind, "sk": storage_key,
                "mt": media_type, "sz": size_bytes, "sha": sha256, "h": request_hash, "pid": prov_id,
            },
        )  # fmt: skip
        if hooks is not None and hooks.after_insert is not None:
            hooks.after_insert(conn)
        row = conn.execute(text(f"SELECT {_COLS} {_FROM} WHERE a.id = :i"), {"i": asset_id}).one()
        return PublishResult(_record(row), created=True)

    try:
        return run_transaction(
            engine,
            op,
            lock_timeout_ms=lock_timeout_ms,
            # a concurrent identical request: restart, and the existing-asset lookup then succeeds
            retry_also=lambda e: sqlstate(e) == "23505" and constraint_name(e) == REQUEST_CONSTRAINT,
            **_retry_kw(backoff),
        )
    except RetryBudgetExhaustedError as exc:
        raise AssetBusyError(str(exc)) from exc
    except DBAPIError as exc:
        if sqlstate(exc) == "23503" and constraint_name(exc) in {
            "data_asset_aoi_project_fk",
            "data_asset_job_fk",
        }:
            raise PublishRefusedError("target_deleted") from exc  # §7.6: the target vanished
        raise


# ------------------------------------------------------------------------------------------ reads
@dataclass(frozen=True)
class JobTarget:
    """What a worker needs to know about its job and AOI before it fetches anything."""

    aoi_id: UUID
    project_id: UUID
    status: str
    locked_by: str | None
    cancel_requested: bool
    aoi_geojson: str  # the AOI polygon as GeoJSON text (EPSG:4326)


def load_job_target(engine: Engine, job_id: UUID) -> JobTarget | None:
    """The job's AOI binding, current flags and AOI geometry; None if the job or its AOI is gone."""
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT j.aoi_id, j.project_id, j.status, j.locked_by, j.cancel_requested, "
                "ST_AsGeoJSON(a.geom) AS geojson FROM job j JOIN aoi a "
                "ON a.id = j.aoi_id AND a.project_id = j.project_id WHERE j.id = :j"
            ),
            {"j": job_id},
        ).first()
    if row is None:
        return None
    return JobTarget(row.aoi_id, row.project_id, row.status, row.locked_by, row.cancel_requested, row.geojson)


def get_asset(engine: Engine, asset_id: UUID) -> AssetRecord | None:
    with engine.connect() as c:
        row = c.execute(text(f"SELECT {_COLS} {_FROM} WHERE a.id = :i"), {"i": asset_id}).first()
    return None if row is None else _record(row)


def list_assets(
    engine: Engine,
    *,
    project_id: UUID | None = None,
    aoi_id: UUID | None = None,
    job_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AssetRecord], int]:
    where: list[str] = []
    params: dict[str, Any] = {"l": limit, "o": offset}
    for col, val in (("project_id", project_id), ("aoi_id", aoi_id), ("job_id", job_id)):
        if val is not None:
            where.append(f"a.{col} = :{col}")
            params[col] = val
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with engine.connect() as c:
        total = c.execute(text(f"SELECT count(*) FROM data_asset a {clause}"), params).scalar_one()
        rows = c.execute(
            text(f"SELECT {_COLS} {_FROM} {clause} ORDER BY a.created_at, a.id LIMIT :l OFFSET :o"), params
        ).all()
    return [_record(r) for r in rows], int(total)


# ----------------------------------------- single-asset delete
def delete_asset(
    engine: Engine,
    asset_id: UUID,
    *,
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    backoff: Callable[[int], None] | None = None,
) -> str:
    """Delete one asset row and its provenance, tombstoning its file, in one transaction (ADR-0014 §8).

    The file is removed after the commit by `drain_tombstones`; a failure of that cleanup never fails
    this deletion. An asset of a queued/running job is refused (the job may still be publishing). Returns
    the storage key that was tombstoned.
    """

    def op(conn: Connection) -> str:
        row = conn.execute(
            text(
                "SELECT id, job_id, storage_key, provenance_id FROM data_asset WHERE id = :i FOR "
                "UPDATE "
                "NOWAIT"
            ),
            {"i": asset_id},
        ).first()
        if row is None:
            raise AssetNotFoundError(str(asset_id))
        if row.job_id is not None:
            st = conn.execute(
                text("SELECT status FROM job WHERE id = :j"), {"j": row.job_id}
            ).scalar_one_or_none()
            if st in ("queued", "running"):
                raise AssetJobActiveError(str(row.job_id))
        conn.execute(
            text("SELECT id FROM provenance WHERE id = :p FOR UPDATE NOWAIT"), {"p": row.provenance_id}
        )
        conn.execute(
            text(
                "INSERT INTO storage_tombstone (storage_key) VALUES (:k) ON CONFLICT (storage_key) DO NOTHING"
            ),
            {"k": row.storage_key},
        )
        if conn.execute(text("DELETE FROM data_asset WHERE id = :i"), {"i": asset_id}).rowcount != 1:
            raise AssetBusyError("unexpected row count")
        if conn.execute(text("DELETE FROM provenance WHERE id = :p"), {"p": row.provenance_id}).rowcount != 1:
            raise AssetBusyError("unexpected row count")
        return str(row.storage_key)

    try:
        return run_transaction(engine, op, lock_timeout_ms=lock_timeout_ms, **_retry_kw(backoff))
    except RetryBudgetExhaustedError as exc:
        raise AssetBusyError(str(exc)) from exc


# ------------------------------------------------------------------------------------------ tombstones
@dataclass(frozen=True)
class DrainReport:
    removed: int
    failed: int
    remaining: int


def tombstone_pending(engine: Engine, storage_key: str) -> bool:
    with engine.connect() as c:
        return (
            c.execute(
                text("SELECT 1 FROM storage_tombstone WHERE storage_key = :k"), {"k": storage_key}
            ).first()
            is not None
        )


def pending_tombstones(engine: Engine) -> int:
    with engine.connect() as c:
        return int(c.execute(text("SELECT count(*) FROM storage_tombstone")).scalar_one())


def drain_tombstones(engine: Engine, storage: StorageBackend, *, limit: int = DRAIN_BATCH) -> DrainReport:
    """Process up to `limit` tombstones: lock one (`SKIP LOCKED`), re-check that no row references the
    key, delete the file (a missing file is success) and then the tombstone. Idempotent; concurrent
    drains are safe. A failure increments `attempts`/`last_error` and leaves the tombstone for a later
    run."""
    removed = failed = 0
    seen: set[str] = set()
    for _ in range(limit):
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT storage_key FROM storage_tombstone WHERE NOT (storage_key = ANY(CAST(:s AS "
                    "text[]))) "
                    "ORDER BY created_at, storage_key LIMIT 1 FOR UPDATE SKIP LOCKED"
                ),
                {"s": sorted(seen)},
            ).first()
            if row is None:
                break
            key = row.storage_key
            seen.add(key)
            try:
                if conn.execute(text("SELECT 1 FROM data_asset WHERE storage_key = :k"), {"k": key}).first():
                    raise RuntimeError("a data_asset row still references this key; file kept")
                storage.delete(key)
                conn.execute(text("DELETE FROM storage_tombstone WHERE storage_key = :k"), {"k": key})
                removed += 1
            except Exception as exc:  # recorded, never raised: a committed deletion must not fail
                log.warning("tombstone cleanup failed", extra={"storage_key": key})
                conn.execute(
                    text(
                        "UPDATE storage_tombstone SET attempts = attempts + 1, "
                        "last_error = :e WHERE storage_key = :k"
                    ),
                    {"e": f"{type(exc).__name__}: {exc}"[:500], "k": key},
                )
                failed += 1
    return DrainReport(removed, failed, pending_tombstones(engine))


# -------------------------------------------- own-file cleanup
def drain_at_startup(engine: Engine, storage_root: str) -> None:
    """Best-effort tombstone drain when a service starts (ADR-0014 §8). Never raises: cleanup trouble is
    logged and the tombstones stay for the next trigger."""
    try:
        report = drain_tombstones(engine, LocalStorage(storage_root))
        if report.removed or report.failed:
            log.info("startup tombstone drain: removed=%d failed=%d", report.removed, report.failed)
    except Exception:
        log.exception("startup tombstone drain failed; tombstones stay pending")


def cleanup_own_files(
    storage: StorageBackend, key: str, *, attempts: int = CLEANUP_ATTEMPTS, pause: float = 0.05
) -> bool:
    """Bounded removal of the worker's own, newly allocated key and its staging file. Touches nothing
    else: never scans, never deletes by pattern or age. Returns False (and logs) if every attempt
    failed; the file is then left for the report-only reconciliation."""
    for attempt in range(1, attempts + 1):
        try:
            storage.delete(key)
            storage.delete_staging(key)
            return True
        except OSError:
            log.warning(
                "own-file cleanup failed (attempt %d/%d)", attempt, attempts, extra={"storage_key": key}
            )
            if attempt < attempts:
                time.sleep(pause)
    return False


# ------------------------------------- reconcile (report only)
@dataclass(frozen=True)
class ReconcileReport:
    unreferenced_files: list[str]  # stored, but no data_asset row and no tombstone references the key
    rows_missing_file: list[str]  # data_asset ids whose file is absent
    staging_files: list[tuple[str, float, bool]]  # (name, age seconds, older than 24 h)
    pending_tombstones: int


def reconcile_report(engine: Engine, storage: StorageBackend, *, now: float | None = None) -> ReconcileReport:
    """Report only: never deletes, repairs or moves anything."""
    with engine.connect() as c:
        rows = c.execute(text("SELECT id, storage_key FROM data_asset")).all()
        tomb = {r[0] for r in c.execute(text("SELECT storage_key FROM storage_tombstone"))}
    referenced = {r.storage_key for r in rows}
    unreferenced = [k for k in storage.iter_keys() if k not in referenced and k not in tomb]
    missing = [str(r.id) for r in rows if not storage.exists(r.storage_key)]
    t = time.time() if now is None else now
    staging = [(n, max(0.0, t - m), (t - m) > STALE_STAGING_SECONDS) for n, m, _ in storage.iter_staging()]
    return ReconcileReport(unreferenced, missing, staging, len(tomb))
