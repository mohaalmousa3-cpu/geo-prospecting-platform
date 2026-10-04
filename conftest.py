from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

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
