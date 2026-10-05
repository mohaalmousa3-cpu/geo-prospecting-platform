"""Whole-transaction retry and database-error inspection (ADR-0014 §7.6, revision 5).

* An operation is a function of a fresh connection/transaction. On a retryable error the transaction is rolled
  back and the *whole function* is restarted; nothing is ever issued on a connection whose transaction
  aborted.
* One total attempt budget per invocation (`MAX_TX_ATTEMPTS`), shared by all retryable causes; no nested
  counters.
* Errors are inspected by SQLSTATE *and* constraint name (taken from the driver's fields), never by
  SQLSTATE alone.

Generic utility: no domain logic (ADR-0011).
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

MAX_TX_ATTEMPTS = 3  # total attempts per invocation (the first plus at most two restarts)
DEFAULT_LOCK_TIMEOUT_MS = 5000
RETRYABLE_SQLSTATES = frozenset({"40P01", "40001", "55P03"})  # deadlock, serialization, lock not available


def _fields(exc: BaseException) -> dict[str, Any]:
    orig = exc.orig if isinstance(exc, DBAPIError) else exc
    args = getattr(orig, "args", ())
    return args[0] if args and isinstance(args[0], dict) else {}


def sqlstate(exc: BaseException) -> str | None:
    return _fields(exc).get("C")


def constraint_name(exc: BaseException) -> str | None:
    return _fields(exc).get("n")


class RetryBudgetExhaustedError(Exception):
    """All attempts failed with retryable errors; `last` is the final one."""

    def __init__(self, last: BaseException, attempts: int) -> None:
        super().__init__(f"transaction not completed after {attempts} attempts (SQLSTATE {sqlstate(last)})")
        self.last = last
        self.attempts = attempts

    @property
    def last_sqlstate(self) -> str | None:
        return sqlstate(self.last)


def _jitter(attempt: int) -> None:
    time.sleep(random.uniform(0, 0.05 * 2**attempt))  # noqa: S311 - back-off jitter, not security


def run_transaction[T](
    engine: Engine,
    fn: Callable[[Connection], T],
    *,
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    attempts: int = MAX_TX_ATTEMPTS,
    retry_also: Callable[[DBAPIError], bool] | None = None,
    retry_on: tuple[type[BaseException], ...] = (),
    backoff: Callable[[int], None] = _jitter,
) -> T:
    """Run `fn` in a fresh transaction, restarting the whole function on retryable errors.

    `retry_also` lets a caller treat one more database error (e.g. `23503` seen by a delete) as retryable, and
    `retry_on` does the same for named non-database exceptions (e.g. an unexpected affected-row count); both
    consume the same budget. Non-retryable errors, and domain exceptions raised by `fn`, propagate after
    the rollback.
    """
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            with engine.begin() as conn:
                conn.execute(text(f"SET LOCAL lock_timeout = {int(lock_timeout_ms)}"))
                return fn(conn)
        except DBAPIError as exc:
            if sqlstate(exc) in RETRYABLE_SQLSTATES or (retry_also is not None and retry_also(exc)):
                last = exc
                if attempt < attempts:
                    backoff(attempt)
                continue
            raise
        except retry_on as exc:
            last = exc
            if attempt < attempts:
                backoff(attempt)
    assert last is not None
    raise RetryBudgetExhaustedError(last, attempts)
