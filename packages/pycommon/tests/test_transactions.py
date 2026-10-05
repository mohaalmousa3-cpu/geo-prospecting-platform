from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from geo_common.transactions import (
    MAX_TX_ATTEMPTS,
    RetryBudgetExhaustedError,
    constraint_name,
    run_transaction,
    sqlstate,
)

pytestmark = pytest.mark.integration


def _err(code: str, constraint: str | None = None) -> DBAPIError:
    fields = {"C": code, "M": "simulated"} | ({"n": constraint} if constraint else {})
    return DBAPIError("simulated", {}, Exception(fields))  # type: ignore[arg-type]


def test_budget_is_three_total_attempts() -> None:
    assert MAX_TX_ATTEMPTS == 3


def test_sqlstate_and_constraint_come_from_the_driver_fields() -> None:
    e = _err("23503", "job_aoi_project_fk")
    assert (sqlstate(e), constraint_name(e)) == ("23503", "job_aoi_project_fk")
    assert sqlstate(ValueError("x")) is None


def test_restart_on_retryable_error_then_success(db_engine: Engine) -> None:
    calls: list[int] = []

    def fn(conn):  # type: ignore[no-untyped-def]
        calls.append(1)
        if len(calls) < 3:
            raise _err("40P01")
        return conn.execute(text("SELECT 7")).scalar_one()

    assert run_transaction(db_engine, fn, backoff=lambda _n: None) == 7 and len(calls) == 3


def test_budget_exhaustion_raises_with_the_last_error(db_engine: Engine) -> None:
    calls: list[int] = []

    def fn(conn):  # type: ignore[no-untyped-def]
        calls.append(1)
        raise _err("55P03")

    with pytest.raises(RetryBudgetExhaustedError) as ei:
        run_transaction(db_engine, fn, backoff=lambda _n: None)
    assert len(calls) == 3 and ei.value.last_sqlstate == "55P03"


def test_non_retryable_errors_and_domain_errors_propagate_without_retry(db_engine: Engine) -> None:
    calls: list[int] = []

    def boom(conn):  # type: ignore[no-untyped-def]
        calls.append(1)
        raise _err("23514")

    with pytest.raises(DBAPIError):
        run_transaction(db_engine, boom, backoff=lambda _n: None)
    assert len(calls) == 1

    def domain(conn):  # type: ignore[no-untyped-def]
        calls.append(1)
        raise KeyError("domain")

    with pytest.raises(KeyError):
        run_transaction(db_engine, domain)
    assert len(calls) == 2


def test_a_failed_attempt_leaves_no_effect(db_engine: Engine) -> None:
    def fn(conn):  # type: ignore[no-untyped-def]
        conn.execute(text("INSERT INTO project (name) VALUES ('should-vanish')"))
        raise _err("40001")

    with pytest.raises(RetryBudgetExhaustedError):
        run_transaction(db_engine, fn, backoff=lambda _n: None)
    with db_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM project WHERE name='should-vanish'")).scalar_one() == 0
