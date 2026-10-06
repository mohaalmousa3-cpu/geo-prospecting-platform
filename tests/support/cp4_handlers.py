"""Handlers for the CP4 end-to-end tests (import-path registered; they run inside the runner's spawn child).

They wrap the *real* registered handler; nothing here replaces connector or publication logic.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

WATCH = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto")


def publish_then_die(payload: dict[str, Any], context: dict[str, Any]) -> Any:
    """Real handler, then a real process death (`os._exit`) once per marker file: the asset is published and
    committed, but the runner never receives the result. The runner must treat this as a retryable failure."""
    from geo_connectors.handler import catalog_search

    out = catalog_search(payload, context)
    marker = Path(os.environ["CP4_MARKER"])
    if not marker.exists():
        marker.write_text("died after publication")
        os._exit(137)
    return out


def audited_catalog_search(payload: dict[str, Any], context: dict[str, Any]) -> Any:
    """Real handler under a `sys.addaudithook` that records every socket event with the fetch-window flag.
    The events are written to `$CP4_AUDIT_OUT` for the parent test to check (an audit, not a firewall)."""
    from geo_connectors.contracts import in_fetch_window

    events: list[dict[str, Any]] = []

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event in WATCH:
            shown = args[1:] if event in ("socket.connect", "socket.sendto") else args
            events.append(
                {"event": event, "args": [str(x) for x in shown], "in_fetch_window": in_fetch_window()}
            )

    sys.addaudithook(hook)
    from geo_connectors.handler import catalog_search

    out = catalog_search(payload, context)
    Path(os.environ["CP4_AUDIT_OUT"]).write_text(json.dumps(events))
    return out
