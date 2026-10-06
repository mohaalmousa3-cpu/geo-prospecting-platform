from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # lets tests import network_guard / helpers


# ---- shared fixtures of the loopback TLS transport tests (Phase 3b R8) -----------------------------------------
import ipaddress  # noqa: E402
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from local_tls import HOST, Pki, TlsServer, make_pki  # noqa: E402

from geo_connectors import egress_policy as _ep  # noqa: E402


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Pki:
    return make_pki(tmp_path_factory.mktemp("pki"))


@pytest.fixture
def allow_loopback_for_these_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt-in (`pytestmark = usefixtures(...)`): the offline policy refuses loopback (R-b); to exercise a real socket
    the address classifier is patched for 127.0.0.0/8 inside the tests that ask for it. Every other policy step is the
    real code."""
    original = _ep.forbidden_reason

    def patched(addr: _ep.IPAddress) -> str | None:
        if isinstance(addr, ipaddress.IPv4Address) and addr in ipaddress.ip_network("127.0.0.0/8"):
            return None
        return original(addr)

    monkeypatch.setattr(_ep, "forbidden_reason", patched)


@pytest.fixture
def server(pki: Pki) -> Iterator[TlsServer]:
    with TlsServer(pki, HOST) as s:
        yield s
