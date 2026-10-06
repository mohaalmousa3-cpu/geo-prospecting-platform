"""Migration 0004 (T1) and the job-level database integrity rules (T2, direct SQL). ADR-0014 §7.1–§7.3.

Asset-related T2 cases (asset constraints, asset↔job consistency) are pending migration 0005.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.db import downgrade_base, upgrade_head
from geo_common.transactions import constraint_name, sqlstate

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _start_from_empty_tables(db_engine: Engine) -> None:
    """Migration tests move the schema up and down; other tests leave rows behind (some of which a downgrade
    refuses to destroy or an upgrade refuses to guess about). Each test here starts from empty tables."""
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))


MakeAoi = Callable[..., tuple[UUID, UUID]]

CONSTRAINTS = {
    "aoi_id_project_id_key",
    "job_aoi_project_both_or_neither",
    "job_non_noop_requires_aoi",
    "job_aoi_project_fk",
    "job_id_aoi_project_key",
}


def _constraints(engine: Engine) -> set[str]:
    with engine.connect() as c:
        return {
            r[0]
            for r in c.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid IN ('job'::regclass, 'aoi'::regclass) "
                    "AND conname = ANY(:n)"
                ),
                {"n": sorted(CONSTRAINTS)},
            )
        }


def _job_columns(engine: Engine) -> set[str]:
    with engine.connect() as c:
        return {
            r[0]
            for r in c.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='job'")
            )
        }


# --------------------------------------------------------------------------------- T1 migration
def test_up_down_up_on_an_empty_table(db_engine: Engine) -> None:
    with db_engine.begin() as c:  # other tests leave rows behind; this one is about an empty table
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))
    downgrade_base(TEST_URL, "0003")
    assert not _constraints(db_engine) & (
        CONSTRAINTS - {"aoi_id_project_id_key"}
    ) and "aoi_id" not in _job_columns(db_engine)
    upgrade_head(TEST_URL)
    assert _constraints(db_engine) == CONSTRAINTS and {"aoi_id", "project_id"} <= _job_columns(db_engine)
    downgrade_base(TEST_URL, "0003")
    upgrade_head(TEST_URL)
    assert _constraints(db_engine) == CONSTRAINTS


def test_up_with_noop_rows_only_keeps_them(db_engine: Engine) -> None:
    downgrade_base(TEST_URL, "0003")
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job CASCADE"))
        c.execute(text("INSERT INTO job (type) VALUES ('noop'), ('noop')"))
    upgrade_head(TEST_URL)
    with db_engine.connect() as c:
        rows = c.execute(text("SELECT aoi_id, project_id FROM job")).all()
    assert len(rows) == 2 and all(r == (None, None) for r in rows)
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job CASCADE"))


def test_a_non_noop_row_aborts_atomically_and_lists_its_id(db_engine: Engine) -> None:
    downgrade_base(TEST_URL, "0003")
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job CASCADE"))
        jid = c.execute(text("INSERT INTO job (type) VALUES ('boom') RETURNING id")).scalar_one()
        c.execute(text("INSERT INTO job (type) VALUES ('noop')"))
    with pytest.raises(RuntimeError, match="migration 0004 aborted") as ei:
        upgrade_head(TEST_URL)
    assert str(jid) in str(ei.value) and "type=boom" in str(ei.value)
    # nothing half-applied: still the 0003 schema, rows intact, no guessing / deletion
    assert not _constraints(db_engine) & (CONSTRAINTS - {"aoi_id_project_id_key"})
    assert "aoi_id" not in _job_columns(db_engine)
    with db_engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM job")).scalar_one() == 2
        c.execute(text("DELETE FROM job WHERE type='boom'"))  # the owner's explicit remedy, then re-run
    upgrade_head(TEST_URL)
    assert _constraints(db_engine) == CONSTRAINTS
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job CASCADE"))


def test_downgrade_removes_columns_and_constraints(db_engine: Engine) -> None:
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))
    downgrade_base(TEST_URL, "0003")
    assert "project_id" not in _job_columns(db_engine)
    assert "aoi_id_project_id_key" not in _constraints(db_engine)
    upgrade_head(TEST_URL)


# --------------------------------------------------------------------------------- T2 direct SQL (job level)
JOB_FOR_AOI = "INSERT INTO job (type, aoi_id, project_id) VALUES ('catalog_search', :a, :p)"


def _fails(engine: Engine, sql: str, state: str, constraint: str, **params: object) -> None:
    with pytest.raises(DBAPIError) as ei, engine.begin() as c:
        c.execute(text(sql), params)
    assert (sqlstate(ei.value), constraint_name(ei.value)) == (state, constraint)


def test_job_with_a_project_that_differs_from_its_aois_fails(engine: Engine, make_aoi: MakeAoi) -> None:
    _, aoi = make_aoi()
    other_project, _ = make_aoi()
    _fails(engine, JOB_FOR_AOI, "23503", "job_aoi_project_fk", a=aoi, p=other_project)


def test_half_null_pair_fails(engine: Engine, make_aoi: MakeAoi) -> None:
    p, aoi = make_aoi()
    _fails(
        engine,
        "INSERT INTO job (type, aoi_id) VALUES ('noop', :a)",
        "23514",
        "job_aoi_project_both_or_neither",
        a=aoi,
    )
    _fails(
        engine,
        "INSERT INTO job (type, project_id) VALUES ('noop', :p)",
        "23514",
        "job_aoi_project_both_or_neither",
        p=p,
    )


def test_non_noop_job_without_an_aoi_fails_and_noop_with_nulls_succeeds(engine: Engine) -> None:
    _fails(engine, "INSERT INTO job (type) VALUES ('catalog_search')", "23514", "job_non_noop_requires_aoi")
    with engine.begin() as c:
        c.execute(text("INSERT INTO job (type) VALUES ('noop')"))


def test_matching_job_succeeds(engine: Engine, make_aoi: MakeAoi) -> None:
    p, aoi = make_aoi()
    with engine.begin() as c:
        c.execute(text(JOB_FOR_AOI), {"a": aoi, "p": p})


def test_changing_aoi_project_while_referenced_fails_but_not_when_unreferenced(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    p, referenced = make_aoi()
    _, unreferenced = make_aoi(p)
    new_project, _ = make_aoi()
    with engine.begin() as c:
        c.execute(text(JOB_FOR_AOI), {"a": referenced, "p": p})
    _fails(
        engine,
        "UPDATE aoi SET project_id = :n WHERE id = :a",
        "23503",
        "job_aoi_project_fk",
        n=new_project,
        a=referenced,
    )
    # Documents the actual protection: the database does NOT block the same change for an unreferenced AOI;
    # that case is blocked only by the application policy (no API moves an AOI, ADR-0014 §7.4).
    with engine.begin() as c:
        c.execute(text("UPDATE aoi SET project_id = :n WHERE id = :a"), {"n": new_project, "a": unreferenced})
