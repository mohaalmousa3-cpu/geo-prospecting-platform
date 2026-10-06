"""Integration helpers: a fixture-covered AOI, running catalog_search jobs, settings for the fixture mode."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from geo_common.config import Settings

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")
W = "worker-1"
PAYLOAD = {"start": "2026-01-01", "end": "2026-12-31", "collections": ["synthetic-optical"]}
SQUARE = "POLYGON((10.0 40.0,10.1 40.0,10.1 40.1,10.0 40.1,10.0 40.0))"  # overlaps the synthetic footprints


def fixture_aoi(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    with engine.begin() as c:
        p = c.execute(text("INSERT INTO project (name) VALUES ('p') RETURNING id")).scalar_one()
        a = c.execute(
            text(
                "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) "
                "VALUES (:p, 'fx', ST_GeomFromText(:g, 4326), 'polygon', 1, 4, 'EPSG:32631') RETURNING id"
            ),
            {"p": p, "g": SQUARE},
        ).scalar_one()
    return p, a


def running_job(engine: Engine, aoi: uuid.UUID, worker: str = W, status: str = "running") -> uuid.UUID:
    with engine.begin() as c:
        return c.execute(  # type: ignore[no-any-return]
            text(
                "INSERT INTO job (type, status, locked_by, aoi_id, project_id) "
                "SELECT 'catalog_search', :s, :w, a.id, a.project_id FROM aoi a WHERE a.id = :a RETURNING id"
            ),
            {"s": status, "w": worker, "a": aoi},
        ).scalar_one()


def context(job: uuid.UUID, worker: str = W) -> dict[str, Any]:
    return {"job_id": str(job), "worker_id": worker}


def settings_for(storage_root: Path, mode: str = "fixture") -> Settings:
    return Settings(_env_file=None, CONNECTOR_MODE=mode, STORAGE_LOCAL_PATH=str(storage_root))  # type: ignore[arg-type]


def count(engine: Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def db_env() -> dict[str, str]:
    """POSTGRES_* variables that make `Settings.database_url` point at the test database."""
    u = make_url(TEST_URL)
    return {
        "POSTGRES_HOST": str(u.host),
        "POSTGRES_PORT": str(u.port or 5432),
        "POSTGRES_USER": str(u.username),
        "POSTGRES_PASSWORD": str(u.password),
        "POSTGRES_DB": str(u.database),
    }
