"""Connector-scoped no-external-network tests (plan T5).

(a) the guard blocks sockets and name resolution only inside a connector fetch window, so other code (including
    PostgreSQL connections of fixtures and queue threads) is unaffected;
(b) a subprocess audit-hook run records every socket event while the registry and the fixture connector run, and
    requires that there are none. The worker-path variant (destinations restricted to the test PostgreSQL endpoint,
    no event with a geo_connectors frame) arrives with the handler checkpoint; here no database is involved, so the
    allowed set is empty;
(c) the static import check is in tests/unit/test_architecture.py.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest
from helpers import ctx
from network_guard import NetworkAccessError, guard_connector_network

from geo_connectors.contracts import Connector, FetchContext, FetchResult, SourceMetadata
from geo_connectors.errors import ConnectorsDisabled, LiveModeNotAvailable
from geo_connectors.registry import resolve_connector

REPO = Path(__file__).resolve().parents[3]


class Leaky(Connector):
    """A deliberately bad connector: tries the network inside fetch()."""

    name = "leaky"

    def __init__(self, how: str) -> None:
        self.how = how

    def _fetch(self, ctx: FetchContext) -> FetchResult:
        if self.how == "connect":
            socket.socket().connect(("127.0.0.1", 9))
        elif self.how == "create_connection":
            socket.create_connection(("127.0.0.1", 9), timeout=0.1)
        elif self.how == "dns":
            socket.getaddrinfo("example.invalid", 80)
        elif self.how == "unix":
            socket.socket(socket.AF_UNIX).connect("/nonexistent.sock")
        return FetchResult((), SourceMetadata("l", "fixture", "d", "1", "t", {"k": 1}, "0", True))


@pytest.mark.parametrize("how", ["connect", "create_connection", "dns", "unix"])
def test_guard_blocks_network_inside_a_fetch(how: str) -> None:
    with guard_connector_network(), pytest.raises(NetworkAccessError):
        Leaky(how).fetch(ctx())


def test_guard_is_inert_outside_the_window_and_restores_originals() -> None:
    orig = socket.getaddrinfo
    with guard_connector_network():
        # outside any fetch: real resolution of a literal address works (no network needed)
        assert socket.getaddrinfo("127.0.0.1", 80)
    assert socket.getaddrinfo is orig


def test_guard_does_not_affect_other_threads() -> None:
    seen: list[object] = []
    with guard_connector_network():

        def other() -> None:
            seen.append(socket.getaddrinfo("127.0.0.1", 80))

        class Slow(Leaky):
            def _fetch(self, c: FetchContext) -> FetchResult:
                t = threading.Thread(target=other)
                t.start()
                t.join()  # the thread runs while this thread is inside the fetch window
                return super()._fetch(c)

        Slow("none").fetch(ctx())
    assert seen and seen[0]


def test_guard_without_leak_lets_the_fixture_connector_run() -> None:
    with guard_connector_network():
        res = resolve_connector("fixture", "fixture").fetch(ctx())
    assert res.records


_AUDIT_SCRIPT = textwrap.dedent(
    """
    import json, sys, traceback
    from datetime import date
    events = []
    WATCH = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto", "socket.bind")
    def hook(event, args):
        if event in WATCH:
            events.append({"event": event, "frames": [f.filename for f in traceback.extract_stack()]})
    sys.addaudithook(hook)
    from geo_connectors.contracts import FetchContext
    from geo_connectors.errors import ConnectorsDisabled, LiveModeNotAvailable
    from geo_connectors.registry import resolve_connector
    aoi = {"type": "Polygon", "coordinates": [[[10.0, 40.0], [10.1, 40.0], [10.1, 40.1], [10.0, 40.1], [10.0, 40.0]]]}
    c = FetchContext(aoi, date(2026, 1, 1), date(2026, 12, 31), ("synthetic-optical",), 20, 365)
    out = {}
    for mode in ("disabled", "fixture", "live"):
        try:
            out[mode] = len(resolve_connector(mode, "fixture").fetch(c).records)
        except (ConnectorsDisabled, LiveModeNotAvailable) as e:
            out[mode] = type(e).__name__
    print(json.dumps({"events": events, "out": out}))
    """
)


def test_subprocess_audit_records_no_socket_event_in_any_mode() -> None:
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _AUDIT_SCRIPT],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        cwd=REPO,
    )
    doc = json.loads(p.stdout.strip().splitlines()[-1])
    assert doc["events"] == [], doc["events"]  # allowed destinations: none (no database in this path)
    assert doc["out"]["disabled"] == ConnectorsDisabled.__name__
    assert doc["out"]["live"] == LiveModeNotAvailable.__name__
    assert isinstance(doc["out"]["fixture"], int) and doc["out"]["fixture"] > 0
