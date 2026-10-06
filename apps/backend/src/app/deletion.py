"""AOI and project deletion (ADR-0014 §7.5 revision 5, with assets, provenance and tombstones).

One transaction per attempt, the global lock order level by level (project → AOIs → jobs → assets →
provenance), whole-transaction restarts within one total attempt budget (`geo_common.transactions`):

* the unlocked status read is *diagnostic only* (it picks the fast 409; nothing is decided by it alone);
* all relevant job rows are locked with `FOR UPDATE NOWAIT` and the deletion decision uses the
  statuses returned from those locked rows;
* **results guard** (owner decision 2026-10-06): after the active-job protection and before anything
  destructive, any `result` row (or result-side `provenance` row) that references the locked job ids
  refuses the deletion with `HasResultsError`, whatever the cascade flag says. The `ON DELETE CASCADE`
  on `result.job_id` is never relied on as application policy;
* order of refusals: active jobs → results → cascade flag. Conditions that no flag can lift come first;
* assets and their provenance rows are locked `NOWAIT` and tombstoned in the same transaction; rows
  are deleted by the exact locked id sets and affected-row counts are checked (a mismatch restarts);
* RESTRICT foreign keys remain the last line of defence (`23503` on a delete restarts within the
  same budget);
* the deleter never takes the enqueue advisory lock (level 0);
* after the commit the tombstones are drained best effort. A failed cleanup never fails the deletion;
  the number of files still pending is returned for internal logging/tests (the HTTP routes keep 204).

`NOWAIT` avoids waiting for the job/asset/provenance row locks. It does not mean the whole operation
never waits (the project and AOI lock requests can wait, bounded by `lock_timeout`) and it does not
claim that every deadlock is impossible.

`DeletionHooks` is a test seam for deterministic interleavings and simulated faults; production code
never sets it.
"""

# ruff: noqa: S608  (table names and ORDER BY lists are constants of this module; values are bound)

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.assets_pg import drain_tombstones
from geo_common.queue import JobStatus
from geo_common.storage import StorageBackend
from geo_common.transactions import (
    DEFAULT_LOCK_TIMEOUT_MS,
    RetryBudgetExhaustedError,
    constraint_name,
    run_transaction,
    sqlstate,
)

log = logging.getLogger("app.deletion")
ACTIVE = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)  # everything else is terminal


class TargetNotFoundError(Exception):
    pass


class HasActiveJobsError(Exception):
    def __init__(self, count: int) -> None:
        super().__init__(f"{count} queued or running job(s) reference this target; cancel them first")
        self.count = count


class HasResultsError(Exception):
    def __init__(self, results: int) -> None:
        super().__init__(
            f"{results} scientific result record(s) reference this target's jobs; "
            "results are never deleted by AOI/project deletion"
        )
        self.results = results


class NeedsCascadeError(Exception):
    def __init__(self, jobs: int, assets: int = 0) -> None:
        super().__init__(
            f"{jobs} job(s) and {assets} staged asset(s) depend on this AOI; "
            "pass the explicit cascade flag to delete them"
        )
        self.jobs, self.assets = jobs, assets


class NotEmptyError(Exception):
    def __init__(self, aoi_count: int) -> None:
        super().__init__(f"project still contains {aoi_count} AOI(s)")
        self.aoi_count = aoi_count


class StillReferencedError(Exception):
    def __init__(self, constraint: str | None) -> None:
        super().__init__(f"a referencing row still exists (constraint {constraint})")
        self.constraint = constraint


class RetryLaterError(Exception):
    pass


class IntegrityFailureError(Exception):
    """An unexpected integrity error: surfaced (500 `integrity_error`), never hidden or mapped to 404."""

    def __init__(self, state: str | None, constraint: str | None) -> None:
        super().__init__(f"unexpected integrity failure (SQLSTATE {state}, constraint {constraint})")
        self.state, self.constraint = state, constraint


class _CountMismatchError(Exception):
    """A DELETE affected a different number of rows than the locked id set: restart the transaction."""


@dataclass
class DeletionHooks:
    """Test seam: callbacks run inside the deletion transaction at fixed points (not for production)."""

    after_parent_lock: Callable[[Connection], None] | None = None  # project/AOI rows locked
    after_diagnostic_read: Callable[[Connection], None] | None = None  # unlocked status read done
    after_job_locks: Callable[[Connection], None] | None = None  # job rows locked, nothing deleted
    after_asset_locks: Callable[[Connection], None] | None = None  # asset/provenance rows locked
    before_statement: Callable[[str], None] | None = None  # called with each statement kind


@dataclass
class DeletionOptions:
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS
    hooks: DeletionHooks | None = None
    backoff: Callable[[int], None] | None = None
    storage: StorageBackend | None = None  # when set, tombstones are drained after the commit


@dataclass(frozen=True)
class DeletionResult:
    tombstoned: int  # files whose rows were deleted in the transaction
    files_pending_cleanup: int  # tombstones still pending after the best-effort drain


def _hook(opts: DeletionOptions, name: str, conn: Connection) -> None:
    h = opts.hooks
    if h is not None and (fn := getattr(h, name)) is not None:
        fn(conn)


def _x(conn: Connection, opts: DeletionOptions, label: str, sql: str, **params: Any) -> Any:
    if opts.hooks is not None and opts.hooks.before_statement is not None:
        opts.hooks.before_statement(label)
    return conn.execute(text(sql), params)


def _ids(values: list[UUID]) -> list[str]:
    return [str(v) for v in values]


def _decide_active(rows: list[Any]) -> None:
    active = [r for r in rows if r.status in ACTIVE]
    if active:
        raise HasActiveJobsError(len(active))


def _results_guard(conn: Connection, opts: DeletionOptions, job_ids: list[UUID], aoi_ids: list[UUID]) -> None:
    """Refuse if scientific records reference the target jobs (owner decision, 2026-10-06).

    Counted, per target job (the locked jobs of the AOI(s) being deleted):

    * every `result` row; and
    * every `provenance` row that is **not** owned by a `data_asset` of the AOI(s) selected for deletion.
      Provenance of a selected asset is deleted explicitly with that asset in the same transaction (accepted
      asset lifecycle) and is therefore neither refused nor counted. Provenance owned by an asset of any
      other AOI, or by no asset, is protected like a result.

    Each row is counted once. The AOI rows are locked by the caller, so no asset can be published into the
    selected AOIs while this query and the later deletion run.
    """
    if not job_ids:
        return
    n = _x(
        conn,
        opts,
        "results_guard",
        "SELECT (SELECT count(*) FROM result WHERE job_id = ANY(CAST(:j AS uuid[]))) "
        "+ (SELECT count(*) FROM provenance p WHERE p.job_id = ANY(CAST(:j AS uuid[])) "
        "AND NOT EXISTS (SELECT 1 FROM data_asset a WHERE a.provenance_id = p.id "
        "AND a.aoi_id = ANY(CAST(:a AS uuid[]))))",
        j=_ids(job_ids),
        a=_ids(aoi_ids),
    ).scalar_one()
    if n:
        raise HasResultsError(int(n))


def _lock_assets(conn: Connection, opts: DeletionOptions, where: str, order: str, **p: Any) -> list[Any]:
    """Lock the assets (NOWAIT), then their provenance rows (NOWAIT); returns the asset rows."""
    assets: list[Any] = _x(
        conn,
        opts,
        "asset_lock",
        f"SELECT id, storage_key, provenance_id FROM data_asset WHERE {where} "
        f"ORDER BY {order} FOR UPDATE NOWAIT",
        **p,
    ).all()
    if assets:
        _x(
            conn,
            opts,
            "provenance_lock",
            "SELECT id FROM provenance WHERE id = ANY(CAST(:p AS uuid[])) ORDER BY id FOR UPDATE NOWAIT",
            p=_ids([a.provenance_id for a in assets]),
        )
    _hook(opts, "after_asset_locks", conn)
    return assets


def _delete_by_ids(conn: Connection, opts: DeletionOptions, label: str, table: str, ids: list[UUID]) -> None:
    if not ids:
        return
    n = _x(
        conn,
        opts,
        label,
        f"DELETE FROM {table} WHERE id = ANY(CAST(:ids AS uuid[]))",
        ids=_ids(ids),
    ).rowcount
    if n != len(ids):
        raise _CountMismatchError


def _tombstone_and_delete_assets(conn: Connection, opts: DeletionOptions, assets: list[Any]) -> int:
    if not assets:
        return 0
    keys = sorted({a.storage_key for a in assets})
    _x(
        conn,
        opts,
        "tombstones",
        "INSERT INTO storage_tombstone (storage_key) SELECT unnest(CAST(:k AS text[])) "
        "ON CONFLICT (storage_key) DO NOTHING",
        k=keys,
    )
    _delete_by_ids(conn, opts, "asset_delete", "data_asset", [a.id for a in assets])
    _delete_by_ids(conn, opts, "provenance_delete", "provenance", [a.provenance_id for a in assets])
    return len(keys)


def _run(engine: Engine, opts: DeletionOptions, fn: Callable[[Connection], int]) -> DeletionResult:
    kw: dict[str, Any] = {}
    if opts.backoff is not None:
        kw["backoff"] = opts.backoff
    try:
        tombstoned = run_transaction(
            engine,
            fn,
            lock_timeout_ms=opts.lock_timeout_ms,
            retry_also=lambda e: sqlstate(e) == "23503",  # a RESTRICT reference appeared: restart
            retry_on=(_CountMismatchError,),
            **kw,
        )
    except RetryBudgetExhaustedError as exc:
        if sqlstate(exc.last) == "23503":
            raise StillReferencedError(constraint_name(exc.last)) from exc
        raise RetryLaterError(str(exc)) from exc
    except DBAPIError as exc:
        if (sqlstate(exc) or "").startswith("23"):
            raise IntegrityFailureError(sqlstate(exc), constraint_name(exc)) from exc
        raise
    return DeletionResult(tombstoned, _drain(engine, opts, tombstoned))


def _drain(engine: Engine, opts: DeletionOptions, tombstoned: int) -> int:
    """Best-effort post-commit cleanup. Never raises: the committed deletion stays a success."""
    if not tombstoned or opts.storage is None:
        return tombstoned
    try:
        report = drain_tombstones(engine, opts.storage)
    except Exception:
        log.exception("post-commit tombstone drain failed; files stay pending")
        return tombstoned
    if report.remaining:
        log.warning("files pending cleanup after deletion: %d", report.remaining)
    return report.remaining


def delete_aoi(
    engine: Engine, aoi_id: UUID, *, cascade: bool, options: DeletionOptions | None = None
) -> DeletionResult:
    """Delete one AOI. `cascade` is the explicit flag that also deletes its jobs and staged assets."""
    opts = options or DeletionOptions()
    key = {"i": aoi_id}

    def op(conn: Connection) -> int:
        # (1) level 2: the AOI row
        if _x(conn, opts, "aoi_lock", "SELECT id FROM aoi WHERE id = :i FOR UPDATE", **key).first() is None:
            raise TargetNotFoundError(str(aoi_id))
        _hook(opts, "after_parent_lock", conn)
        # (2) diagnostic, unlocked: picks the fast 409; the decision is taken on locked rows below
        _decide_active(
            _x(conn, opts, "diagnostic", "SELECT id, status FROM job WHERE aoi_id = :i", **key).all()
        )
        _hook(opts, "after_diagnostic_read", conn)
        # (3) level 3: all the AOI's jobs, never waiting; statuses come from the locked rows
        jobs = _x(
            conn,
            opts,
            "job_lock",
            "SELECT id, status FROM job WHERE aoi_id = :i ORDER BY id FOR UPDATE NOWAIT",
            **key,
        ).all()
        _decide_active(jobs)
        job_ids = [r.id for r in jobs]
        _hook(opts, "after_job_locks", conn)
        # (3b) results guard: after the active-job protection, before anything destructive
        _results_guard(conn, opts, job_ids, [aoi_id])
        # (4) cascade flag (unlocked count: the AOI lock froze the membership of its dependents)
        n_assets = _x(conn, opts, "asset_count", "SELECT count(*) FROM data_asset WHERE aoi_id = :i", **key)
        n_assets = int(n_assets.scalar_one())
        if (job_ids or n_assets) and not cascade:
            raise NeedsCascadeError(len(job_ids), n_assets)
        # (5)-(7) assets, provenance, tombstones; then delete by the exact locked id sets
        assets = _lock_assets(conn, opts, "aoi_id = :i", "id", **key)
        tombstoned = _tombstone_and_delete_assets(conn, opts, assets)
        _delete_by_ids(conn, opts, "job_delete", "job", job_ids)
        if _x(conn, opts, "aoi_delete", "DELETE FROM aoi WHERE id = :i", **key).rowcount != 1:
            raise _CountMismatchError
        return tombstoned

    return _run(engine, opts, op)


def delete_project(
    engine: Engine, project_id: UUID, *, delete_aois: bool, options: DeletionOptions | None = None
) -> DeletionResult:
    """Delete a project; with `delete_aois` also its AOIs, their jobs and staged assets."""
    opts = options or DeletionOptions()
    key = {"p": project_id}

    def op(conn: Connection) -> int:
        # (1) level 1: the project row
        if (
            _x(conn, opts, "project_lock", "SELECT id FROM project WHERE id = :p FOR UPDATE", **key).first()
            is None
        ):
            raise TargetNotFoundError(str(project_id))
        # (2) level 2: a NEW statement locking every AOI of the project in id order
        aoi_ids = [
            r.id
            for r in _x(
                conn,
                opts,
                "aoi_lock",
                "SELECT id FROM aoi WHERE project_id = :p ORDER BY id FOR UPDATE",
                **key,
            ).all()
        ]
        _hook(opts, "after_parent_lock", conn)
        job_ids: list[UUID] = []
        if aoi_ids:
            a = _ids(aoi_ids)
            # (3) diagnostic, unlocked
            _decide_active(
                _x(
                    conn,
                    opts,
                    "diagnostic",
                    "SELECT id, status FROM job WHERE aoi_id = ANY(CAST(:a AS uuid[]))",
                    a=a,
                ).all()
            )
            _hook(opts, "after_diagnostic_read", conn)
            # (4) level 3: all jobs of those AOIs, never waiting; decision on the locked rows
            jobs = _x(
                conn,
                opts,
                "job_lock",
                "SELECT id, aoi_id, status FROM job WHERE aoi_id = ANY(CAST(:a AS uuid[])) "
                "ORDER BY aoi_id, id FOR UPDATE NOWAIT",
                a=a,
            ).all()
            _decide_active(jobs)
            job_ids = [r.id for r in jobs]
            _hook(opts, "after_job_locks", conn)
            # (4b) results guard (applies whatever the flag says)
            _results_guard(conn, opts, job_ids, aoi_ids)
        # (5) cascade flag (existing `delete_aois=true` semantics, ADR-0013)
        if aoi_ids and not delete_aois:
            raise NotEmptyError(len(aoi_ids))
        # (6)-(8) assets, provenance, tombstones; then delete by the exact locked id sets
        tombstoned = 0
        if aoi_ids:
            assets = _lock_assets(conn, opts, "aoi_id = ANY(CAST(:a AS uuid[]))", "aoi_id, id", a=a)
            tombstoned = _tombstone_and_delete_assets(conn, opts, assets)
            _delete_by_ids(conn, opts, "job_delete", "job", job_ids)
            _delete_by_ids(conn, opts, "aoi_delete", "aoi", aoi_ids)
        if _x(conn, opts, "project_delete", "DELETE FROM project WHERE id = :p", **key).rowcount != 1:
            raise _CountMismatchError
        return tombstoned

    return _run(engine, opts, op)
