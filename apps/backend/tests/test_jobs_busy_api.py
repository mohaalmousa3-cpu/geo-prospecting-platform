"""The public noop jobs endpoint maps an exhausted queue-transaction budget to 503 retry_later (CP2 finding)."""

from __future__ import annotations

import pytest
from db_concurrency import Held
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.main import create_app
from geo_common.config import Settings
from geo_common.queue_pg import PostgresJobQueue

pytestmark = [pytest.mark.integration, pytest.mark.timeout(60)]
ENQUEUE_LOCK = 7_000_001  # the advisory lock `enqueue` takes first (queue_pg._ENQUEUE_LOCK_KEY)


def test_exhausting_the_queue_retry_budget_returns_503_and_then_recovers(engine: Engine) -> None:
    """Deterministic: another session holds the enqueue advisory lock, the queue's lock timeout is 100 ms, so all
    three attempts of the single attempt budget fail with 55P03 (QueueBusyError)."""
    settings = Settings(_env_file=None, CORS_ALLOWED_ORIGINS="http://localhost:3000")
    q = PostgresJobQueue(engine, max_queued_jobs=10, default_max_attempts=2, lock_timeout_ms=100)
    with TestClient(create_app(settings, engine=engine, queue=q)) as client:
        with Held(engine) as holder:
            holder.run("SELECT pg_advisory_xact_lock(:k)", k=ENQUEUE_LOCK)
            r = client.post("/api/v1/jobs", json={"type": "noop", "payload": {}})
            assert r.status_code == 503, r.text
            body = r.json()["error"]
            assert body["code"] == "retry_later" and "queue is busy" in body["message"]
        ok = client.post("/api/v1/jobs", json={"type": "noop", "payload": {}})
        assert ok.status_code == 201  # the lock is free again: the endpoint works, nothing was half-created
    with engine.connect() as c:
        from sqlalchemy import text

        assert c.execute(text("SELECT count(*) FROM job")).scalar_one() == 1


def test_the_public_api_still_offers_no_non_noop_job_creation(engine: Engine) -> None:
    settings = Settings(_env_file=None, CORS_ALLOWED_ORIGINS="http://localhost:3000")
    with TestClient(create_app(settings, engine=engine)) as client:
        r = client.post("/api/v1/jobs", json={"type": "catalog_search", "payload": {}})
        assert r.status_code == 422
