"""Handler registry and the `noop` handler.

Handlers are referenced by import path ("module:function") so they can be imported inside the
child process. A handler takes the job payload and returns a HandlerResult. Engines added in
later phases register themselves here; Phase 1 has only `noop` (no scientific output).
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

NOOP_MAX_SLEEP_SECONDS = 60.0

DEFAULT_HANDLERS: dict[str, str] = {"noop": "runner.handlers:noop"}


@dataclass(frozen=True)
class HandlerResult:
    status: str = "succeeded"  # "succeeded" | "insufficient_data"
    message: str | None = None


Handler = Callable[[dict[str, Any]], HandlerResult]


def noop(payload: dict[str, Any]) -> HandlerResult:
    """Does nothing (optionally sleeps). Produces no result of any kind."""
    seconds = float(payload.get("sleep_seconds", 0))
    if not 0 <= seconds <= NOOP_MAX_SLEEP_SECONDS:
        raise ValueError(f"sleep_seconds must be within 0..{NOOP_MAX_SLEEP_SECONDS}")
    time.sleep(seconds)
    return HandlerResult()


def load_handler(path: str) -> Handler:
    module, _, attr = path.partition(":")
    fn = getattr(importlib.import_module(module), attr)
    return fn  # type: ignore[no-any-return]
