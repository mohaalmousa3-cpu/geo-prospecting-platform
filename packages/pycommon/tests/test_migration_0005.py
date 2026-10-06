"""Migration 0005 and the asset-level database integrity rules (T1 for 0005, T2 asset cases; direct SQL)."""

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


@pytest.fixture(autouse=True)
def _start_from_empty_tables(db_engine: Engine) -> None:
    """Migration tests move the schema up and down; other tests leave rows behind (some of which a downgrade
    refuses to destroy or an upgrade refuses to guess about). Each test here starts from empty tables."""
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))


MakeAoi = Callable[..., tuple[uuid.UUID, uuid.UUID]]
AddJob = Callable[..., uuid.UUID]

FKS = {"data_asset_aoi_project_fk", "data_asset_job_fk", "data_asset_provenance_fk"}
OTHER = {
    "data_asset_storage_key_key", "data_asset_provenance_key", "data_asset_kind_known",
    "data_asset_size_nonnegative", "data_asset_sha256_hex", "data_asset_request_hash_format",
    "storage_tombstone_pkey",
}  # fmt: skip


def _tables(engine: Engine) -> set[str]:
    with engine.connect() as c:
        return {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}


def _nullable(engine: Engine, table: str) -> str:
    with engine.connect() as c:
        return str(
            c.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = 'job_id'"
                ),
                {"t": table},
            ).scalar_one()
        )


# ------------------------------------------------------------------------------- T1 migration 0005
def test_up_down_up_and_nullability(db_engine: Engine) -> None:
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))
    downgrade_base(TEST_URL, "0004")
    assert not {"data_asset", "storage_tombstone"} & _tables(db_engine)
    assert _nullable(db_engine, "provenance") == "NO"
    upgrade_head(TEST_URL)
    assert {"data_asset", "storage_tombstone"} <= _tables(db_engine)
    assert _nullable(db_engine, "provenance") == "YES"  # option A
    assert _nullable(db_engine, "result") == "NO"  # results always need a job


def test_downgrade_refuses_to_destroy_assets_and_says_why(
    db_engine: Engine,
    engine: Engine,
    make_aoi: MakeAoi,
    assets,  # type: ignore[no-untyped-def]
) -> None:
    _, aoi = make_aoi()
    assets.add(aoi, file=False)  # job-less asset, therefore a provenance row with job_id NULL
    with pytest.raises(RuntimeError, match="migration 0005 downgrade aborted") as ei:
        downgrade_base(TEST_URL, "0004")
    assert "1 data_asset" in str(ei.value) and "provenance.job_id" in str(ei.value)
    assert "data_asset" in _tables(db_engine)  # nothing was dropped
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))
    downgrade_base(TEST_URL, "0004")
    upgrade_head(TEST_URL)


def test_constraints_are_immediate_enabled_validated_and_restrict(engine: Engine) -> None:
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT conname, contype, condeferrable, convalidated, confdeltype, confupdtype, confmatchtype, "
                "(SELECT bool_and(tgenabled = 'O') FROM pg_trigger t WHERE t.tgconstraint = c.oid) AS enabled "
                "FROM pg_constraint c WHERE conrelid IN ('data_asset'::regclass, 'storage_tombstone'::regclass)"
            )
        ).all()
    by = {r.conname: r for r in rows}
    assert FKS | OTHER <= set(by)
    for name in FKS:
        r = by[name]
        assert (r.contype, r.condeferrable, r.convalidated, r.enabled) == ("f", False, True, True), name
        assert (r.confdeltype, r.confupdtype, r.confmatchtype) == ("r", "r", "s"), name
    assert all(not r.condeferrable and r.convalidated for r in rows)
    with engine.connect() as c:
        idx = c.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'data_asset_job_request_key'")
        ).scalar_one()
    assert "UNIQUE" in idx and "(job_id, kind, request_hash)" in idx and "WHERE (job_id IS NOT NULL)" in idx


# ------------------------------------------------------------------------------- T2 asset cases
def _asset_sql(**over: object) -> tuple[str, dict[str, object]]:
    p = {
        "id": uuid.uuid4(), "p": None, "a": None, "j": None, "k": f"k/{uuid.uuid4()}", "kind": "scene_catalog",
        "sha": "0" * 64, "h": "v1:" + "a" * 64, "pv": None,
    }  # fmt: skip
    p.update(over)
    return (
        "INSERT INTO data_asset (id, project_id, aoi_id, job_id, kind, storage_key, media_type, size_bytes, "
        "sha256, request_hash, provenance_id) VALUES (:id, :p, :a, :j, :kind, :k, 'application/json', 1, :sha, "
        ":h, :pv)",
        p,
    )


def _prov(c, job: uuid.UUID | None = None) -> uuid.UUID:  # type: ignore[no-untyped-def]
    return c.execute(  # type: ignore[no-any-return]
        text("INSERT INTO provenance (job_id, record) VALUES (:j, '{}'::jsonb) RETURNING id"), {"j": job}
    ).scalar_one()


def _fails(engine: Engine, state: str, constraint: str | None, **over: object) -> None:
    with pytest.raises(DBAPIError) as ei, engine.begin() as c:
        if over.get("pv") is None:
            over["pv"] = _prov(c)
        sql, params = _asset_sql(**over)
        c.execute(text(sql), params)
    assert sqlstate(ei.value) == state
    if constraint:
        assert constraint_name(ei.value) == constraint


def test_asset_requires_project_and_aoi(engine: Engine, make_aoi: MakeAoi) -> None:
    p, a = make_aoi()
    _fails(engine, "23502", None, p=None, a=a)
    _fails(engine, "23502", None, p=p, a=None)


def test_asset_project_must_match_its_aois_project(engine: Engine, make_aoi: MakeAoi) -> None:
    _, a = make_aoi()
    other, _ = make_aoi()
    _fails(engine, "23503", "data_asset_aoi_project_fk", p=other, a=a)


def test_asset_job_must_belong_to_the_same_aoi_and_project(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p1, a1 = make_aoi()
    _, a2 = make_aoi()
    job_in_a2 = add_job(a2, "running")
    _fails(engine, "23503", "data_asset_job_fk", p=p1, a=a1, j=job_in_a2)


def test_asset_without_a_job_succeeds_and_may_carry_job_less_provenance(
    engine: Engine, make_aoi: MakeAoi
) -> None:
    p, a = make_aoi()
    with engine.begin() as c:
        pv = _prov(c)  # provenance.job_id NULL (option A)
        sql, params = _asset_sql(p=p, a=a, pv=pv)
        c.execute(text(sql), params)


def test_asset_for_its_own_job_succeeds(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> None:
    p, a = make_aoi()
    job = add_job(a, "running")
    with engine.begin() as c:
        sql, params = _asset_sql(p=p, a=a, j=job, pv=_prov(c, job))
        c.execute(text(sql), params)


def test_storage_key_is_unique_and_immutable(engine: Engine, make_aoi: MakeAoi) -> None:
    p, a = make_aoi()
    with engine.begin() as c:
        sql, params = _asset_sql(p=p, a=a, k="same/key", pv=_prov(c))
        c.execute(text(sql), params)
    _fails(engine, "23505", "data_asset_storage_key_key", p=p, a=a, k="same/key")
    with pytest.raises(DBAPIError, match="immutable") as ei, engine.begin() as c:
        c.execute(text("UPDATE data_asset SET storage_key = 'other/key'"))
    assert sqlstate(ei.value) == "23514"


def test_request_uniqueness_applies_to_job_bound_assets_only(
    engine: Engine, make_aoi: MakeAoi, add_job: AddJob
) -> None:
    p, a = make_aoi()
    job = add_job(a, "running")
    with engine.begin() as c:
        for _ in range(2):  # job-less assets may repeat the same request hash
            sql, params = _asset_sql(p=p, a=a, pv=_prov(c))
            c.execute(text(sql), params)
        sql, params = _asset_sql(p=p, a=a, j=job, pv=_prov(c, job))
        c.execute(text(sql), params)
    _fails(engine, "23505", "data_asset_job_request_key", p=p, a=a, j=job, pv=None)
    # another kind or another job is a different request
    with engine.begin() as c:
        sql, params = _asset_sql(p=p, a=a, j=job, kind="dem_clip", pv=_prov(c, job))
        c.execute(text(sql), params)


@pytest.mark.parametrize(
    ("over", "name"),
    [
        ({"kind": "result"}, "data_asset_kind_known"),
        ({"sha": "xyz"}, "data_asset_sha256_hex"),
        ({"sha": "A" * 64}, "data_asset_sha256_hex"),
        ({"h": "a" * 64}, "data_asset_request_hash_format"),
        ({"h": "v1:short"}, "data_asset_request_hash_format"),
    ],
)
def test_check_constraints(engine: Engine, make_aoi: MakeAoi, over: dict[str, object], name: str) -> None:
    p, a = make_aoi()
    _fails(engine, "23514", name, p=p, a=a, **over)


def test_provenance_cannot_be_shared_by_two_assets(engine: Engine, make_aoi: MakeAoi) -> None:
    p, a = make_aoi()
    with engine.begin() as c:
        pv = _prov(c)
        sql, params = _asset_sql(p=p, a=a, pv=pv)
        c.execute(text(sql), params)
    _fails(engine, "23505", "data_asset_provenance_key", p=p, a=a, pv=pv)


def test_restrict_protects_every_referenced_row(engine: Engine, make_aoi: MakeAoi, add_job: AddJob) -> None:
    p, a = make_aoi()
    job = add_job(a, "succeeded")
    with engine.begin() as c:
        pv = _prov(c, job)
        sql, params = _asset_sql(p=p, a=a, j=job, pv=pv)
        c.execute(text(sql), params)
    # Which of several RESTRICT constraints PostgreSQL reports first is not specified (a job also references
    # the AOI): accept any of the constraints that legitimately protect the row.
    for stmt, constraints in (
        ("DELETE FROM provenance", {"data_asset_provenance_fk"}),
        ("DELETE FROM job", {"data_asset_job_fk"}),
        ("DELETE FROM aoi", {"data_asset_aoi_project_fk", "job_aoi_project_fk"}),
    ):
        with pytest.raises(DBAPIError) as ei, engine.begin() as c:
            c.execute(text(stmt))
        assert sqlstate(ei.value) == "23503" and constraint_name(ei.value) in constraints, stmt


def test_result_rows_still_require_a_job(engine: Engine) -> None:
    with pytest.raises(DBAPIError) as ei, engine.begin() as c:
        c.execute(text("INSERT INTO result (job_id, kind, envelope) VALUES (NULL, 'x', '{}'::jsonb)"))
    assert sqlstate(ei.value) == "23502"
