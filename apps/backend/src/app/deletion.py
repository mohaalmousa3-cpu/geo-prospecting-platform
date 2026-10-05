"""AOI and project deletion (ADR-0014 §7.5 revision 5; job level — assets arrive with migration 0005).

One transaction per attempt, the global lock order level by level (project → AOIs → jobs → assets), whole-
transaction restarts within one total attempt budget (`geo_common.transactions`), and:

* the unlocked status read is *diagnostic only* (it picks the fast 409; nothing is decided by it alone);
* all relevant job rows are locked with `FOR UPDATE NOWAIT` and the deletion decision uses the statuses
returned
  from those locked rows;
* rows are deleted by the exact locked id sets and affected-row counts are checked (a mismatch restarts);
* RESTRICT foreign keys remain the last line of defence (`23503` on a delete restarts within the same budget);
* the deleter never takes the enqueue advisory lock (level 0).

`NOWAIT` avoids waiting for the job row locks. It does not mean the whole operation never waits (the
project and
AOI lock requests can wait, bounded by `lock_timeout`) and it does not claim that every deadlock is
impossible.

`DeletionHooks` is a test seam for deterministic interleavings and simulated faults; production code never
sets it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.queue import JobStatus
from geo_common.transactions import (
    DEFAULT_LOCK_TIMEOUT_MS,
    RetryBudgetExhaustedError,
    constraint_name,
    run_transaction,
    sqlstate,
)

ACTIVE = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)  # everything else is terminal


class TargetNotFoundError(Exception):
    pass


class HasActiveJobsError(Exception):
    def __init__(self, count: int) -> None:
        super().__init__(f"{count} queued or running job(s) reference this target; cancel them first")
        self.count = count


class NeedsCascadeError(Exception):
    def __init__(self, jobs: int) -> None:
        super().__init__(f"{jobs} dependent job(s) exist; pass the explicit cascade flag to delete them")
        self.jobs = jobs


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
    """A DELETE affected a different number of rows than the locked id set: restart the whole transaction."""


@dataclass
class DeletionHooks:
    """Test seam: callbacks run inside the deletion transaction at fixed points (never set in production)."""

    after_parent_lock: Callable[[Connection], None] | None = None  # project/AOI rows locked
    after_diagnostic_read: Callable[[Connection], None] | None = None  # unlocked status read done
    after_job_locks: Callable[[Connection], None] | None = None  # job rows locked, before any delete
    before_statement: Callable[[str], None] | None = None  # called with each statement kind (fault injection)


@dataclass
class DeletionOptions:
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS
    hooks: DeletionHooks | None = None
    backoff: Callable[[int], None] | None = None


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


def _run(engine: Engine, opts: DeletionOptions, fn: Callable[[Connection], None]) -> None:
    kw: dict[str, Any] = {}
    if opts.backoff is not None:
        kw["backoff"] = opts.backoff
    try:
        run_transaction(
            engine,
            fn,
            lock_timeout_ms=opts.lock_timeout_ms,
            retry_also=lambda e: (
                sqlstate(e) == "23503"
            ),  # a RESTRICT reference appeared: restart, same budget
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


def delete_aoi(
    engine: Engine, aoi_id: UUID, *, cascade: bool, options: DeletionOptions | None = None
) -> None:
    """Delete one AOI. `cascade` is the explicit flag that also deletes its (terminal) jobs."""
    opts = options or DeletionOptions()
    key = {"i": aoi_id}

    def op(conn: Connection) -> None:
        # (1) level 2: the AOI row
        if _x(conn, opts, "aoi_lock", "SELECT id FROM aoi WHERE id = :i FOR UPDATE", **key).first() is None:
            raise TargetNotFoundError(str(aoi_id))
        _hook(opts, "after_parent_lock", conn)
        # (2) diagnostic, unlocked: picks the fast 409; the decision is taken on locked rows below
        diag = _x(conn, opts, "diagnostic", "SELECT id, status FROM job WHERE aoi_id = :i", **key).all()
        _decide_active(diag)
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
        # (4) cascade flag
        if job_ids and not cascade:
            raise NeedsCascadeError(len(job_ids))
        # (5)-(6) assets and tombstones: added with migration 0005 (not part of this checkpoint)
        # (7) delete by the exact locked id sets; counts must match
        if job_ids:
            n = _x(
                conn,
                opts,
                "job_delete",
                "DELETE FROM job WHERE id = ANY(CAST(:ids AS uuid[]))",
                ids=_ids(job_ids),
            ).rowcount
            if n != len(job_ids):
                raise _CountMismatchError
        if _x(conn, opts, "aoi_delete", "DELETE FROM aoi WHERE id = :i", **key).rowcount != 1:
            raise _CountMismatchError

    _run(engine, opts, op)


def delete_project(
    engine: Engine, project_id: UUID, *, delete_aois: bool, options: DeletionOptions | None = None
) -> None:
    """Delete a project; with `delete_aois` also its AOIs and their (terminal) jobs."""
    opts = options or DeletionOptions()

    def op(conn: Connection) -> None:
        # (1) level 1: the project row
        key = {"p": project_id}
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
        jobs: list[Any] = []
        if aoi_ids:
            # (3) diagnostic, unlocked
            diag = _x(
                conn,
                opts,
                "diagnostic",
                "SELECT id, status FROM job WHERE aoi_id = ANY(CAST(:a AS uuid[]))",
                a=_ids(aoi_ids),
            ).all()
            _decide_active(diag)
            _hook(opts, "after_diagnostic_read", conn)
            # (4) level 3: all jobs of those AOIs, never waiting; decision on the locked rows
            jobs = _x(
                conn,
                opts,
                "job_lock",
                "SELECT id, aoi_id, status FROM job WHERE aoi_id = ANY(CAST(:a AS uuid[])) "
                "ORDER BY aoi_id, id FOR UPDATE NOWAIT",
                a=_ids(aoi_ids),
            ).all()
            _decide_active(jobs)
            _hook(opts, "after_job_locks", conn)
        # (5) cascade flag (existing `delete_aois=true` semantics, ADR-0013)
        if aoi_ids and not delete_aois:
            raise NotEmptyError(len(aoi_ids))
        # (6)-(7) assets and tombstones: added with migration 0005 (not part of this checkpoint)
        # (8) delete by the exact locked id sets, checking counts
        if jobs:
            n = _x(
                conn,
                opts,
                "job_delete",
                "DELETE FROM job WHERE id = ANY(CAST(:ids AS uuid[]))",
                ids=_ids([r.id for r in jobs]),
            ).rowcount
            if n != len(jobs):
                raise _CountMismatchError
        if aoi_ids:
            n = _x(
                conn,
                opts,
                "aoi_delete",
                "DELETE FROM aoi WHERE id = ANY(CAST(:ids AS uuid[]))",
                ids=_ids(aoi_ids),
            ).rowcount
            if n != len(aoi_ids):
                raise _CountMismatchError
        if _x(conn, opts, "project_delete", "DELETE FROM project WHERE id = :p", **key).rowcount != 1:
            raise _CountMismatchError

    _run(engine, opts, op)
