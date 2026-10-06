"""Migration 0006: result/provenance -> job foreign keys are RESTRICT (owner option B). Real PostgreSQL, direct SQL."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.db import downgrade_base, upgrade_head
from geo_common.transactions import constraint_name, sqlstate

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")
pytestmark = pytest.mark.integration
NAMES = ("result_job_id_fkey", "provenance_job_id_fkey")
MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]


@pytest.fixture(autouse=True)
def _empty_and_at_head(db_engine: Engine) -> None:
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))


def actions(engine: Engine) -> dict[str, tuple[str, str, bool, bool]]:
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT conname, confdeltype, confupdtype, condeferrable, convalidated FROM pg_constraint "
                "WHERE conname = ANY(:n)"
            ),
            {"n": list(NAMES)},
        ).all()
    return {r.conname: (r.confdeltype, r.confupdtype, r.condeferrable, r.convalidated) for r in rows}


def seed(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> uuid.UUID:
    _, aoi = make_aoi()
    job = add_job(aoi, "succeeded")
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO result (job_id, kind, envelope) VALUES (:j, 'x', '{}'::jsonb)"), {"j": job}
        )
        c.execute(text("INSERT INTO provenance (job_id, record) VALUES (:j, '{}'::jsonb)"), {"j": job})
    return job


def test_both_constraints_are_restrict_immediate_and_validated_at_head(engine: Engine) -> None:
    assert actions(engine) == {n: ("r", "r", False, True) for n in NAMES}


def test_up_down_up_and_the_downgrade_loses_no_rows(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    job = seed(engine, make_aoi, add_job)
    try:
        downgrade_base(TEST_URL, "0005")
        assert {k: v[0] for k, v in actions(engine).items()} == {n: "c" for n in NAMES}  # CASCADE again
        with engine.connect() as c:  # a downgrade changes no rows
            assert (
                c.execute(text("SELECT count(*) FROM result WHERE job_id = :j"), {"j": job}).scalar_one() == 1
            )
    finally:
        upgrade_head(TEST_URL)
    assert actions(engine) == {n: ("r", "r", False, True) for n in NAMES}
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM provenance WHERE job_id = :j"), {"j": job}).scalar_one() == 1
        )


@pytest.mark.parametrize(("table", "name"), [("result", NAMES[0]), ("provenance", NAMES[1])])
def test_raw_delete_of_a_job_with_records_is_refused_and_changes_nothing(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob, table: str, name: str
) -> None:
    job = seed(engine, make_aoi, add_job)
    with pytest.raises(DBAPIError) as err, engine.begin() as c:
        c.execute(text("DELETE FROM job WHERE id = :j"), {"j": job})
    # which of the two RESTRICT keys PostgreSQL reports first is not specified: either is a refusal
    assert sqlstate(err.value) == "23503" and constraint_name(err.value) in NAMES
    with engine.connect() as c:
        counts = c.execute(
            text(
                "SELECT (SELECT count(*) FROM job), (SELECT count(*) FROM result), (SELECT count(*) FROM provenance)"
            )
        ).one()
    assert tuple(counts) == (1, 1, 1)
    assert name in NAMES and table in ("result", "provenance")


def test_explicit_order_works_and_a_job_without_records_deletes_normally(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    job = seed(engine, make_aoi, add_job)
    with engine.begin() as c:
        c.execute(text("DELETE FROM result WHERE job_id = :j"), {"j": job})
        c.execute(text("DELETE FROM provenance WHERE job_id = :j"), {"j": job})
        c.execute(text("DELETE FROM job WHERE id = :j"), {"j": job})
    _, aoi = make_aoi()
    free = add_job(aoi, "succeeded")
    with engine.begin() as c:
        assert c.execute(text("DELETE FROM job WHERE id = :j"), {"j": free}).rowcount == 1


def test_truncate_cascade_is_an_administrative_operation_outside_the_foreign_keys(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    """Documented limit, not protection: a foreign-key action cannot stop TRUNCATE ... CASCADE."""
    seed(engine, make_aoi, add_job)
    with engine.begin() as c:
        c.execute(text("TRUNCATE job CASCADE"))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM result")).scalar_one() == 0
