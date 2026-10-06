from __future__ import annotations

import os

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.db import downgrade_base, upgrade_head

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _start_from_empty_tables(db_engine: Engine) -> None:
    """Migration tests move the schema up and down; other tests leave rows behind (some of which a downgrade
    refuses to destroy or an upgrade refuses to guess about). Each test here starts from empty tables."""
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project, storage_tombstone, provenance, result CASCADE"))


def test_up_down_up_and_postgis(db_engine: Engine) -> None:
    downgrade_base(TEST_URL)
    with db_engine.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    assert not {"aoi", "job", "result", "provenance"} & tables
    upgrade_head(TEST_URL)
    with db_engine.begin() as c:
        c.execute(text("INSERT INTO project (name) VALUES ('p')"))
        assert c.execute(text("SELECT extname FROM pg_extension WHERE extname='postgis'")).scalar_one()
        c.execute(
            text(
                "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) VALUES "
                "((SELECT id FROM project), 't', ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))',4326), 'polygon', 1, 4, 'EPSG:32631')"
            )
        )
        srid = c.execute(text("SELECT ST_SRID(geom) FROM aoi")).scalar_one()
        assert srid == 4326
        c.execute(text("DELETE FROM aoi"))
        c.execute(text("DELETE FROM project"))


def test_status_constraint(engine: Engine) -> None:
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("INSERT INTO job (type, status) VALUES ('noop', 'confirmed')"))


AOI_INSERT = (
    "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) VALUES "
    "(:p, 'a', ST_GeomFromText(:g, 4326), 'polygon', 1, 4, 'EPSG:32631')"
)
SQUARE = "POLYGON((0 0,1 0,1 1,0 1,0 0))"


def _project(engine: Engine) -> str:
    with engine.begin() as c:
        return str(c.execute(text("INSERT INTO project (name) VALUES ('p') RETURNING id")).scalar_one())


def test_aoi_rejects_wrong_geometry_type(engine: Engine) -> None:
    pid = _project(engine)
    with pytest.raises(DBAPIError, match="Geometry type"), engine.begin() as c:
        c.execute(text(AOI_INSERT), {"p": pid, "g": "POINT(0 0)"})


def test_aoi_requires_an_existing_project(engine: Engine) -> None:
    with pytest.raises(DBAPIError, match="null value|violates"), engine.begin() as c:
        c.execute(text(AOI_INSERT), {"p": None, "g": SQUARE})
    with pytest.raises(DBAPIError, match="foreign key"), engine.begin() as c:
        c.execute(text(AOI_INSERT), {"p": "00000000-0000-0000-0000-000000000000", "g": SQUARE})


def test_project_with_aois_cannot_be_deleted_at_db_level(engine: Engine) -> None:
    pid = _project(engine)
    with engine.begin() as c:
        c.execute(text(AOI_INSERT), {"p": pid, "g": SQUARE})
    with pytest.raises(DBAPIError, match="foreign key"), engine.begin() as c:
        c.execute(text("DELETE FROM project WHERE id=:p"), {"p": pid})


def test_project_name_constraints(engine: Engine) -> None:
    for name in ("", "x" * 121):
        with pytest.raises(DBAPIError), engine.begin() as c:
            c.execute(text("INSERT INTO project (name) VALUES (:n)"), {"n": name})


def test_migration_0003_moves_existing_aois_into_a_default_project(db_engine: Engine) -> None:
    downgrade_base(TEST_URL, "0002")  # schema as of Phase 2, no projects
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM aoi"))
        for i in range(2):
            c.execute(
                text(
                    "INSERT INTO aoi (name, geom, source, area_km2, vertex_count, working_crs) VALUES "
                    f"('old{i}', ST_GeomFromText('{SQUARE}', 4326), 'polygon', 1, 4, 'EPSG:32631')"
                )
            )
    upgrade_head(TEST_URL)
    with db_engine.begin() as c:
        rows = c.execute(
            text("SELECT p.name, count(*) FROM aoi a JOIN project p ON p.id=a.project_id GROUP BY 1")
        ).all()
        assert [tuple(r) for r in rows] == [("Default project", 2)]
        c.execute(text("TRUNCATE aoi, project CASCADE"))
    # and with no AOIs at all, no project is invented
    downgrade_base(TEST_URL, "0002")
    upgrade_head(TEST_URL)
    with db_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM project")).scalar_one() == 0
