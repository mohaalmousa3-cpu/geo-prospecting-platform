from __future__ import annotations

import os

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.db import downgrade_base, upgrade_head

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")

pytestmark = pytest.mark.integration


def test_up_down_up_and_postgis(db_engine: Engine) -> None:
    downgrade_base(TEST_URL)
    with db_engine.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    assert not {"aoi", "job", "result", "provenance"} & tables
    upgrade_head(TEST_URL)
    with db_engine.begin() as c:
        assert c.execute(text("SELECT extname FROM pg_extension WHERE extname='postgis'")).scalar_one()
        c.execute(
            text(
                "INSERT INTO aoi (name, geom, source) VALUES "
                "('t', ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))',4326), 'test')"
            )
        )
        srid = c.execute(text("SELECT ST_SRID(geom) FROM aoi")).scalar_one()
        assert srid == 4326
        c.execute(text("DELETE FROM aoi"))


def test_status_constraint(engine: Engine) -> None:
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("INSERT INTO job (type, status) VALUES ('noop', 'confirmed')"))


def test_aoi_rejects_wrong_geometry_type(engine: Engine) -> None:
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(
            text("INSERT INTO aoi (name, geom, source) VALUES ('p', ST_GeomFromText('POINT(0 0)',4326), 't')")
        )
