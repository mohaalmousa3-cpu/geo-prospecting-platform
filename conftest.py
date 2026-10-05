from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from geo_common.config import Settings
from geo_common.db import make_engine, upgrade_head
from geo_common.queue_pg import PostgresJobQueue

TEST_URL = os.environ.get("GEO_TEST_DATABASE_URL", "postgresql+pg8000://geo:geo@localhost:5432/geo_test")


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    engine = make_engine(TEST_URL, pool_size=20)
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"integration tests need PostGIS at GEO_TEST_DATABASE_URL: {exc}")
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    upgrade_head(TEST_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(db_engine: Engine) -> Engine:
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE job, aoi, project CASCADE"))
    return db_engine


@pytest.fixture
def make_aoi(engine: Engine) -> Callable[..., tuple[uuid.UUID, uuid.UUID]]:
    """Factory creating a project (or using the given one) and an AOI; returns (project_id, aoi_id)."""

    def _make(project_id: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID]:
        with engine.begin() as c:
            pid = (
                project_id
                or c.execute(text("INSERT INTO project (name) VALUES ('p') RETURNING id")).scalar_one()
            )
            aid = c.execute(
                text(
                    "INSERT INTO aoi (project_id, name, geom, source, area_km2, vertex_count, working_crs) "
                    "VALUES (:p, 'a', ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))', 4326), "
                    "'polygon', 1, 4, 'EPSG:32631') RETURNING id"
                ),
                {"p": pid},
            ).scalar_one()
        return pid, aid

    return _make


@pytest.fixture
def aoi_id(make_aoi: Callable[..., tuple[uuid.UUID, uuid.UUID]]) -> uuid.UUID:
    """One AOI (in its own project) for tests that need an AOI-bound job."""
    return make_aoi()[1]


@pytest.fixture
def queue(engine: Engine) -> PostgresJobQueue:
    return PostgresJobQueue(engine, max_queued_jobs=10, default_max_attempts=2)


@pytest.fixture
def worker_id() -> str:
    return f"w-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, MAX_QUEUED_JOBS=3, CORS_ALLOWED_ORIGINS="http://localhost:3000")


@pytest.fixture
def client(engine: Engine, settings: Settings) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app(settings, engine=engine)) as c:
        yield c


@pytest.fixture
def add_job(engine: Engine) -> Callable[..., uuid.UUID]:
    """Insert a job row directly (any status) bound to an AOI; returns its id (deletion/concurrency tests)."""

    def _add(aoi: uuid.UUID, status: str = "queued", job_type: str = "catalog_search") -> uuid.UUID:
        with engine.begin() as c:
            return c.execute(  # type: ignore[no-any-return]
                text(
                    "INSERT INTO job (type, status, aoi_id, project_id) "
                    "SELECT :t, :s, a.id, a.project_id FROM aoi a WHERE a.id = :a RETURNING id"
                ),
                {"t": job_type, "s": status, "a": aoi},
            ).scalar_one()

    return _add
