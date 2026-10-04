"""Test-only network guard scoped to connector execution (plan T5a).

While a connector's `fetch()` runs (`geo_connectors.contracts.in_fetch_window()`), any attempt to connect a socket
or resolve a name raises `NetworkAccessError`. Calls outside the window, and calls from other threads (their
`contextvars` flag is unset), pass through to the real implementation, so PostgreSQL connections of fixtures and
queue threads are unaffected. Lives in tests because `geo_connectors` itself must not import `socket`.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from geo_connectors.contracts import in_fetch_window


class NetworkAccessError(AssertionError):
    pass


_SOCKET_METHODS = ("connect", "connect_ex", "sendto")
_MODULE_FUNCS = ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex")


def _wrap(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    def guarded(*args: Any, **kwargs: Any) -> Any:
        if in_fetch_window():
            raise NetworkAccessError(f"network access attempted inside a connector fetch window: {name}")
        return original(*args, **kwargs)

    return guarded


@contextmanager
def guard_connector_network() -> Iterator[None]:
    saved: list[tuple[Any, str, Any]] = []
    try:
        for m in _SOCKET_METHODS:
            orig = getattr(socket.socket, m)
            saved.append((socket.socket, m, orig))
            setattr(socket.socket, m, _wrap(f"socket.{m}", orig))
        for f in _MODULE_FUNCS:
            orig = getattr(socket, f)
            saved.append((socket, f, orig))
            setattr(socket, f, _wrap(f"socket.{f}", orig))
        yield
    finally:
        for owner, attr, orig in reversed(saved):
            setattr(owner, attr, orig)
