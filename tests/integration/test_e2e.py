"""API → job table → worker → API (P1-09 done-when)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from geo_common.queue_pg import PostgresJobQueue
from runner.loop import Runner

pytestmark = pytest.mark.integration


def test_noop_job_end_to_end(client: TestClient, queue: PostgresJobQueue) -> None:
    created = client.post("/api/v1/jobs", json={"type": "noop", "payload": {"sleep_seconds": 0.2}}).json()
    assert client.get(f"/api/v1/jobs/{created['id']}").json()["status"] == "queued"
    runner = Runner(queue, worker_id="e2e", lease_seconds=5, poll_interval=0.05, job_timeout=30)
    assert runner.run_once()
    done = client.get(f"/api/v1/jobs/{created['id']}").json()
    assert done["status"] == "succeeded" and done["attempts"] == 1 and done["finished_at"]
