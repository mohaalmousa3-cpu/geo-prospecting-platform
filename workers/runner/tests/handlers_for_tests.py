"""Handlers used only by tests (import-path registered; run inside the child process)."""

from __future__ import annotations

import os
import time
from typing import Any

from runner.handlers import HandlerResult


def sleeper(payload: dict[str, Any]) -> HandlerResult:
    time.sleep(float(payload.get("s", 30)))
    return HandlerResult()


def boom(payload: dict[str, Any]) -> HandlerResult:
    raise RuntimeError("handler exploded")


def insufficient(payload: dict[str, Any]) -> HandlerResult:
    return HandlerResult("insufficient_data", "no usable scenes")


def hard_crash(payload: dict[str, Any]) -> HandlerResult:
    os._exit(137)


class WantsRetry(Exception):
    retryable = True  # duck-typed: the runner must treat this as a retryable failure


def retry_me(payload: dict[str, Any]) -> HandlerResult:
    raise WantsRetry("temporarily busy")


def echo_context(payload: dict[str, Any], context: dict[str, Any]) -> HandlerResult:
    """Two-argument handler: receives the job context from the runner."""
    import json

    return HandlerResult("succeeded", json.dumps(context, sort_keys=True))


def cancels(payload: dict[str, Any]) -> HandlerResult:
    return HandlerResult("cancelled", "stopped before publication")
