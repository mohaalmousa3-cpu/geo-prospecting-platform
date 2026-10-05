"""`JobQueue.enqueue` contract for AOI-bound jobs (ADR-0014): project derived from the AOI, never supplied."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from geo_common.queue import JobQueue, JobTargetNotFoundError
from geo_common.queue_pg import PostgresJobQueue

pytestmark = pytest.mark.integration
MakeAoi = Callable[..., tuple[UUID, UUID]]


def _jobs(engine: Engine) -> int:
    with engine.connect() as c:
        return int(c.execute(text("SELECT count(*) FROM job")).scalar_one())


def test_non_noop_without_an_aoi_is_rejected_before_any_sql(queue: PostgresJobQueue, engine: Engine) -> None:
    with pytest.raises(ValueError, match="AOI-bound"):
        queue.enqueue("catalog_search")
    assert _jobs(engine) == 0


def test_aoi_bound_job_derives_its_project(queue: PostgresJobQueue, make_aoi: MakeAoi) -> None:
    project, aoi = make_aoi()
    j = queue.enqueue("catalog_search", {"k": 1}, aoi_id=aoi)
    assert (j.aoi_id, j.project_id, j.type) == (aoi, project, "catalog_search")
    assert queue.get(j.id).project_id == project


def test_noop_stays_aoi_free_and_may_optionally_be_bound(queue: PostgresJobQueue, make_aoi: MakeAoi) -> None:
    free = queue.enqueue("noop")
    assert (free.aoi_id, free.project_id) == (None, None)
    project, aoi = make_aoi()
    bound = queue.enqueue("noop", aoi_id=aoi)
    assert (bound.aoi_id, bound.project_id) == (aoi, project)


def test_unknown_aoi_is_a_target_error_and_inserts_nothing(queue: PostgresJobQueue, engine: Engine) -> None:
    with pytest.raises(JobTargetNotFoundError):
        queue.enqueue("catalog_search", aoi_id=uuid4())
    assert _jobs(engine) == 0


def test_the_contract_has_no_project_parameter() -> None:
    for impl in (JobQueue.enqueue, PostgresJobQueue.enqueue):
        assert (
            "project_id" not in inspect.signature(impl).parameters
        )  # the project is derived, never supplied


def test_queue_limit_still_applies_to_aoi_bound_jobs(engine: Engine, make_aoi: MakeAoi) -> None:
    from geo_common.queue import QueueFullError

    _, aoi = make_aoi()
    q = PostgresJobQueue(engine, max_queued_jobs=2, default_max_attempts=2)
    q.enqueue("catalog_search", aoi_id=aoi)
    q.enqueue("catalog_search", aoi_id=aoi)
    with pytest.raises(QueueFullError):
        q.enqueue("catalog_search", aoi_id=aoi)
