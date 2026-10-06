"""AOI/project deletion (ADR-0014 §7.5 revision 5), job level: sequential behaviour, simulated faults, seam checks.

Labels used in this file: *real* = real database behaviour; *simulated* = a fault or state change injected through
the `DeletionHooks` test seam (not evidence of concurrency). Concurrency evidence is in test_deletion_concurrency.py.
Asset-level steps and tombstones arrive with migration 0005 (not part of this checkpoint).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import DBAPIError

from app import deletion  # noqa: F401
from app.deletion import (
    DeletionHooks,
    DeletionOptions,
    HasActiveJobsError,
    IntegrityFailureError,
    NeedsCascadeError,
    NotEmptyError,
    RetryLaterError,
    StillReferencedError,
    TargetNotFoundError,
    delete_aoi,
    delete_project,
)
from geo_common.transactions import constraint_name, sqlstate

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
ACTIVE = ["queued", "running"]
TERMINAL = ["succeeded", "failed", "cancelled", "insufficient_data"]
MakeAoi = Callable[..., tuple[UUID, UUID]]
AddJob = Callable[..., UUID]


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def _quiet() -> DeletionOptions:
    return DeletionOptions(backoff=lambda _n: None)


# ----------------------------------------------------------------------- T-D1 sequential matrix (real)
@pytest.mark.parametrize("status", ACTIVE)
def test_active_job_blocks_aoi_deletion_and_nothing_changes(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, status: str
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, status)
    for cascade in (False, True):  # the flag never overrides the active-job rule
        with pytest.raises(HasActiveJobsError):
            delete_aoi(engine, aoi, cascade=cascade, options=_quiet())
    assert (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)


@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_job_needs_the_cascade_flag_then_is_deleted_with_the_aoi(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, status: str
) -> None:
    pid, aoi = make_aoi()
    add_job(aoi, status)
    with pytest.raises(NeedsCascadeError):
        delete_aoi(engine, aoi, cascade=False, options=_quiet())
    assert (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)
    delete_aoi(engine, aoi, cascade=True, options=_quiet())
    assert (_count(engine, "aoi"), _count(engine, "job"), _count(engine, "project")) == (0, 0, 1)


def test_aoi_without_jobs_is_deleted_without_a_flag_and_missing_aoi_is_not_found(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    _, aoi = make_aoi()
    delete_aoi(engine, aoi, cascade=False)
    with pytest.raises(TargetNotFoundError):
        delete_aoi(engine, aoi, cascade=False)


def test_noop_jobs_without_an_aoi_are_untouched_by_aoi_deletion(
    engine: Engine,
    queue,
    make_aoi: MakeAoi,  # type: ignore[no-untyped-def]
) -> None:
    _, aoi = make_aoi()
    queue.enqueue("noop")
    delete_aoi(engine, aoi, cascade=False)
    assert _count(engine, "job") == 1


@pytest.mark.parametrize("status", ACTIVE)
def test_active_job_in_any_aoi_blocks_project_deletion_atomically(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, status: str
) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi(p)
    _, a3 = make_aoi(p)
    add_job(a1, "succeeded")
    add_job(a3, status)  # the third AOI carries the active job
    with pytest.raises(HasActiveJobsError):
        delete_project(engine, p, delete_aois=True, options=_quiet())
    assert (_count(engine, "project"), _count(engine, "aoi"), _count(engine, "job")) == (1, 3, 2)
    assert a2  # untouched as well


@pytest.mark.parametrize("status", TERMINAL)
def test_project_deletion_with_terminal_jobs(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, status: str
) -> None:
    p, a1 = make_aoi()
    _, a2 = make_aoi(p)
    add_job(a1, status)
    add_job(a2, status)
    with pytest.raises(NotEmptyError) as ei:
        delete_project(engine, p, delete_aois=False, options=_quiet())
    assert ei.value.aoi_count == 2
    delete_project(engine, p, delete_aois=True, options=_quiet())
    assert (_count(engine, "project"), _count(engine, "aoi"), _count(engine, "job")) == (0, 0, 0)


def test_empty_project_and_missing_project(engine: Engine, make_aoi: MakeAoi) -> None:
    p, a = make_aoi()
    delete_aoi(engine, a, cascade=False)
    delete_project(engine, p, delete_aois=False)
    with pytest.raises(TargetNotFoundError):
        delete_project(engine, p, delete_aois=False)


# ----------------------------------------------------------------------- T-D4 state change at the seam (real update, hypothetical path)
def test_status_change_after_the_diagnostic_read_is_caught_on_the_locked_rows(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """A committed update from another session turns a terminal job active between the unlocked read and the lock.

    No such terminal → non-terminal path exists in the code today (T-D14); the update is issued directly to prove
    that the decision uses the locked rows, not the earlier read.
    """
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    fired: list[int] = []

    def flip(_conn) -> None:  # type: ignore[no-untyped-def]
        fired.append(1)
        with engine.begin() as other:  # a second session, committed before the deleter locks the job
            other.execute(text("UPDATE job SET status='queued' WHERE id=:j"), {"j": job})

    opts = DeletionOptions(hooks=DeletionHooks(after_diagnostic_read=flip), backoff=lambda _n: None)
    with pytest.raises(HasActiveJobsError):
        delete_aoi(engine, aoi, cascade=True, options=opts)
    assert fired == [1] and (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)


# ----------------------------------------------------------------------- T-D11 injected faults (simulated)
def _fault(code: str) -> DBAPIError:
    return DBAPIError("simulated", {}, Exception({"C": code, "M": f"simulated {code}"}))  # type: ignore[arg-type]


def _scenario(make_aoi: MakeAoi, add_job: AddJob) -> UUID:
    _, aoi = make_aoi()
    add_job(aoi, "succeeded")
    return aoi


STATEMENTS = [
    "aoi_lock",
    "diagnostic",
    "job_lock",
    "results_guard",
    "asset_count",
    "asset_lock",
    "job_delete",
    "aoi_delete",
]


@pytest.mark.parametrize("code", ["40P01", "40001", "55P03"])
@pytest.mark.parametrize("index", range(len(STATEMENTS)))
def test_simulated_retryable_fault_restarts_the_whole_transaction_once(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, code: str, index: int
) -> None:
    aoi = _scenario(make_aoi, add_job)
    seen: list[str] = []
    events: list[tuple[str, int]] = []
    faulted = {"done": False}

    def before(label: str) -> None:
        seen.append(label)
        if label == STATEMENTS[index] and not faulted["done"]:
            faulted["done"] = True
            events.append(("fault", 0))
            raise _fault(code)

    @event.listens_for(engine, "before_cursor_execute")
    def _exec(conn, cursor, statement, params, context, executemany):  # type: ignore[no-untyped-def]
        events.append(("exec", id(conn.connection.dbapi_connection)))

    @event.listens_for(engine, "rollback")
    def _rb(dbapi_conn):  # type: ignore[no-untyped-def]
        events.append(("rollback", id(dbapi_conn)))

    try:
        delete_aoi(
            engine,
            aoi,
            cascade=True,
            options=DeletionOptions(hooks=DeletionHooks(before_statement=before), backoff=lambda _n: None),
        )
    finally:
        event.remove(engine, "before_cursor_execute", _exec)
        event.remove(engine, "rollback", _rb)
    # whole function restarted: the statement sequence is the prefix up to the fault, then the full sequence again
    assert seen == STATEMENTS[: index + 1] + STATEMENTS
    assert (_count(engine, "aoi"), _count(engine, "job")) == (0, 0)
    # nothing was issued on the aborted transaction: after the fault, the next event is a rollback
    k = events.index(("fault", 0))
    assert events[k + 1][0] == "rollback", events[k : k + 3]


def test_simulated_retryable_faults_exhaust_one_total_budget_then_503(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    aoi = _scenario(make_aoi, add_job)
    attempts: list[str] = []
    codes = iter(["40P01", "40001", "55P03", "40P01"])  # mixed causes share ONE budget of 3

    def before(label: str) -> None:
        if label == "aoi_lock":
            attempts.append(label)
            raise _fault(next(codes))

    with pytest.raises(RetryLaterError):
        delete_aoi(
            engine,
            aoi,
            cascade=True,
            options=DeletionOptions(hooks=DeletionHooks(before_statement=before), backoff=lambda _n: None),
        )
    assert len(attempts) == 3  # MAX_TX_ATTEMPTS, one budget for all causes
    assert (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)  # nothing deleted


def test_simulated_23503_on_delete_shares_the_budget_and_ends_as_still_referenced(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    aoi = _scenario(make_aoi, add_job)
    n = {"c": 0}

    def before(label: str) -> None:
        if label == "aoi_delete":
            n["c"] += 1
            raise DBAPIError("simulated", {}, Exception({"C": "23503", "n": "job_aoi_project_fk", "M": "x"}))  # type: ignore[arg-type]

    with pytest.raises(StillReferencedError) as ei:
        delete_aoi(
            engine,
            aoi,
            cascade=True,
            options=DeletionOptions(hooks=DeletionHooks(before_statement=before), backoff=lambda _n: None),
        )
    assert n["c"] == 3 and ei.value.constraint == "job_aoi_project_fk"
    assert (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)


def test_simulated_unexpected_integrity_error_is_surfaced_not_hidden(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    aoi = _scenario(make_aoi, add_job)

    def before(label: str) -> None:
        if label == "job_delete":
            raise DBAPIError("simulated", {}, Exception({"C": "23514", "n": "some_check", "M": "x"}))  # type: ignore[arg-type]

    with pytest.raises(IntegrityFailureError) as ei:
        delete_aoi(
            engine, aoi, cascade=True, options=DeletionOptions(hooks=DeletionHooks(before_statement=before))
        )
    assert (ei.value.state, ei.value.constraint) == ("23514", "some_check")


def test_unrelated_database_errors_propagate_unchanged(engine: Engine, make_aoi: MakeAoi) -> None:
    _, aoi = make_aoi()

    def before(label: str) -> None:
        if label == "diagnostic":
            raise DBAPIError("simulated", {}, Exception({"C": "42P01", "M": "undefined table"}))  # type: ignore[arg-type]

    with pytest.raises(DBAPIError):
        delete_aoi(
            engine, aoi, cascade=False, options=DeletionOptions(hooks=DeletionHooks(before_statement=before))
        )
    assert _count(engine, "aoi") == 1


# ----------------------------------------------------------------------- T-D15 exact id sets and counts (test seam, simulated)
def test_a_row_added_after_the_lock_is_never_deleted_and_the_restrict_fk_refuses(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "succeeded")

    def add_extra(conn) -> None:  # type: ignore[no-untyped-def]
        conn.execute(
            text(
                "INSERT INTO job (type, aoi_id, project_id) SELECT 'catalog_search', id, project_id FROM aoi WHERE id=:a"
            ),
            {"a": aoi},
        )

    opts = DeletionOptions(hooks=DeletionHooks(after_job_locks=add_extra), backoff=lambda _n: None)
    with pytest.raises(StillReferencedError):
        delete_aoi(engine, aoi, cascade=True, options=opts)
    assert (_count(engine, "aoi"), _count(engine, "job")) == (
        1,
        1,
    )  # every attempt rolled back, extra row too


def test_a_locked_row_that_disappears_causes_a_restart_not_a_partial_delete(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    calls = {"n": 0}

    def remove_locked(conn) -> None:  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:  # first attempt only
            conn.execute(text("DELETE FROM job WHERE id=:j"), {"j": job})

    opts = DeletionOptions(hooks=DeletionHooks(after_job_locks=remove_locked), backoff=lambda _n: None)
    delete_aoi(engine, aoi, cascade=True, options=opts)
    assert calls["n"] == 2 and (_count(engine, "aoi"), _count(engine, "job")) == (0, 0)


def test_a_locked_row_that_disappears_every_attempt_ends_in_retry_later(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    _, aoi = make_aoi()
    add_job(aoi, "succeeded")
    calls = {"n": 0}

    def remove_locked(conn) -> None:  # type: ignore[no-untyped-def]
        calls["n"] += 1
        conn.execute(text("DELETE FROM job WHERE aoi_id=:a"), {"a": aoi})

    opts = DeletionOptions(hooks=DeletionHooks(after_job_locks=remove_locked), backoff=lambda _n: None)
    with pytest.raises(RetryLaterError):
        delete_aoi(engine, aoi, cascade=True, options=opts)
    assert calls["n"] == 3 and (_count(engine, "aoi"), _count(engine, "job")) == (1, 1)


# ----------------------------------------------------------------------- T-D13 database-level protections (real, direct SQL)
def test_foreign_keys_are_immediate_enabled_validated_and_restrict(engine: Engine) -> None:
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT conname, condeferrable, convalidated, confdeltype, confupdtype, "
                "(SELECT bool_and(tgenabled = 'O') FROM pg_trigger t WHERE t.tgconstraint = c.oid) AS enabled "
                "FROM pg_constraint c WHERE contype = 'f' AND conname IN ('job_aoi_project_fk', 'aoi_project_id_fkey')"
            )
        ).all()
    by = {r.conname: r for r in rows}
    assert set(by) == {"job_aoi_project_fk", "aoi_project_id_fkey"}
    for r in rows:
        assert (r.condeferrable, r.convalidated, r.enabled) == (False, True, True), r.conname
        assert (
            (r.confdeltype, r.confupdtype) == ("r", "r")
            if r.conname == "job_aoi_project_fk"
            else r.confdeltype == "r"
        )


def test_restrict_refuses_direct_deletes_of_referenced_rows(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, aoi = make_aoi()
    add_job(aoi, "succeeded")
    with pytest.raises(DBAPIError) as e1, engine.begin() as c:
        c.execute(text("DELETE FROM aoi WHERE id=:a"), {"a": aoi})
    assert (sqlstate(e1.value), constraint_name(e1.value)) == ("23503", "job_aoi_project_fk")
    with pytest.raises(DBAPIError) as e2, engine.begin() as c:
        c.execute(text("DELETE FROM project WHERE id=:p"), {"p": p})
    assert sqlstate(e2.value) == "23503"


# ----------------------------------------------------------------------- T-D14 policy regression checks (not database guarantees)
TERMINAL_GUARDS = ("status='queued'", "status='running'", "status IN ('queued','running')")


def _sql_literals(path: Path) -> list[str]:
    out: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def status_updates_without_a_non_terminal_guard(sql: str) -> list[str]:
    """Statements that UPDATE job SET … without a non-terminal source-status predicate in their WHERE part."""
    bad = []
    for stmt in re.split(r"(?=UPDATE job SET)", re.sub(r"\s+", " ", sql)):
        if not stmt.startswith("UPDATE job SET"):
            continue
        where = stmt.partition(" WHERE ")[2].replace("status = ", "status=")
        if not any(g in where for g in TERMINAL_GUARDS):
            bad.append(stmt[:80])
    return bad


def test_every_job_status_update_has_a_non_terminal_source_predicate() -> None:
    queue_pg = ROOT / "packages/pycommon/src/geo_common/queue_pg.py"
    updates = [s for s in _sql_literals(queue_pg) if "UPDATE job" in s]
    assert len(updates) >= 6  # claim, heartbeat, fail, finish, cancel, requeue_expired
    for s in updates:
        assert not status_updates_without_a_non_terminal_guard(s), s


def test_the_policy_check_can_fail() -> None:
    assert status_updates_without_a_non_terminal_guard("UPDATE job SET status='queued' WHERE id=:i")
    assert not status_updates_without_a_non_terminal_guard(
        "UPDATE job SET status='queued' WHERE id=:i AND status = 'running'"
    )


WRITE_PATTERNS = (
    r"(?:INSERT INTO|UPDATE|DELETE FROM) (job|data_asset|provenance|storage_tombstone|result)\b",
    r'_delete_by_ids\(\s*conn,\s*opts,\s*"[a-z_]+",\s*"(job|data_asset|provenance|aoi)"',
)


def test_only_the_known_modules_write_or_delete_job_asset_and_provenance_rows() -> None:
    """Policy check (not a database guarantee): who may write these tables is an explicit, reviewed list."""
    writers: dict[str, set[str]] = {}
    for rel in ("packages/pycommon/src", "apps/backend/src", "workers"):
        for f in (ROOT / rel).rglob("*.py"):
            if {"tests", "migrations", "__pycache__"} & set(f.parts):
                continue
            code = f.read_text()
            for i, pat in enumerate(WRITE_PATTERNS):
                for m in re.finditer(pat, code):
                    stmt = "BYIDS" if i else " ".join(m.group(0).split()[:-1])
                    writers.setdefault(f"{stmt}:{m.group(1)}", set()).add(f.name)
    assert writers == {
        "UPDATE:job": {"queue_pg.py"},
        "INSERT INTO:job": {"queue_pg.py"},
        "INSERT INTO:data_asset": {"assets_pg.py"},
        "INSERT INTO:provenance": {"assets_pg.py"},
        "INSERT INTO:storage_tombstone": {"assets_pg.py", "deletion.py"},
        "UPDATE:storage_tombstone": {"assets_pg.py"},
        "DELETE FROM:data_asset": {"assets_pg.py"},
        "DELETE FROM:provenance": {"assets_pg.py"},
        "DELETE FROM:storage_tombstone": {"assets_pg.py"},
        "BYIDS:job": {"deletion.py"},
        "BYIDS:data_asset": {"deletion.py"},
        "BYIDS:provenance": {"deletion.py"},
        "BYIDS:aoi": {"deletion.py"},
    }, writers


def test_deletion_code_never_takes_the_enqueue_advisory_lock() -> None:
    src = (ROOT / "apps/backend/src/app/deletion.py").read_text()
    code = re.sub(r'""".*?"""', "", src, flags=re.S)  # the module docstring may mention it
    assert "pg_advisory" not in code and "7_000_001" not in code
