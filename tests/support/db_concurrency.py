"""Deterministic concurrency harness (real database sessions; no `sleep` for synchronisation).

Synchronisation uses observable database state: a thread is "blocked" when `pg_blocking_pids` reports a holder
for one of its backends. Every wait has a bounded timeout (`WAIT_SECONDS`) and fails the test when it expires.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, Engine, text

WAIT_SECONDS = 10.0


def backend_pid(conn: Connection) -> int:
    return int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())


def wait_until(predicate: Callable[[], bool], what: str, timeout: float = WAIT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)  # polling interval only; never used as a synchronisation guess
    raise AssertionError(f"timed out after {timeout}s waiting for: {what}")


def blocked_by(engine: Engine, holder_pid: int) -> int:
    with engine.connect() as c:
        return int(
            c.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE :h = ANY(pg_blocking_pids(pid))"),
                {"h": holder_pid},
            ).scalar_one()
        )


def wait_blocked_by(engine: Engine, holder_pid: int, what: str) -> None:
    wait_until(lambda: blocked_by(engine, holder_pid) > 0, f"a session blocked by pid {holder_pid}: {what}")


class Bg:
    """Run `fn` in a thread; `result()` returns its value or re-raises its exception (bounded join)."""

    def __init__(self, fn: Callable[[], Any], name: str = "bg") -> None:
        self._value: Any = None
        self._exc: BaseException | None = None

        def run() -> None:
            try:
                self._value = fn()
            except BaseException as exc:
                self._exc = exc

        self._t = threading.Thread(target=run, name=name, daemon=True)
        self._t.start()

    @property
    def done(self) -> bool:
        return not self._t.is_alive()

    def result(self, timeout: float = WAIT_SECONDS) -> Any:
        self._t.join(timeout)
        assert not self._t.is_alive(), "background operation did not finish in time"
        if self._exc is not None:
            raise self._exc
        return self._value

    def exception(self, timeout: float = WAIT_SECONDS) -> BaseException | None:
        self._t.join(timeout)
        assert not self._t.is_alive(), "background operation did not finish in time"
        return self._exc


class Held:
    """A raw session with an open transaction; always rolled back and closed, even if the test fails."""

    def __init__(self, engine: Engine) -> None:
        self.conn = engine.connect()
        self.tx = self.conn.begin()
        self.pid = backend_pid(self.conn)

    def run(self, sql: str, **params: object) -> None:
        self.conn.execute(text(sql), params)

    def commit(self) -> None:
        self.tx.commit()

    def __enter__(self) -> Held:
        return self

    def __exit__(self, *exc: object) -> None:
        self.conn.close()


class Gate:
    """A hook that pauses the deleter inside its transaction until the test releases it."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        self.pid: int | None = None

    def __call__(self, conn: Connection) -> None:
        self.pid = backend_pid(conn)
        self.reached.set()
        assert self.release.wait(WAIT_SECONDS), "gate was never released"

    def wait_reached(self) -> int:
        assert self.reached.wait(WAIT_SECONDS), "deleter never reached the gate"
        assert self.pid is not None
        return self.pid
