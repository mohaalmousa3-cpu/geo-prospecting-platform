"""Offline hardening proofs for the urllib3 transport (Phase 3b R8): peer-address assertion and response-header
policy. Loopback TLS servers only (see `local_tls.py`); no DNS, no provider, no non-loopback address."""

from __future__ import annotations

import dataclasses
import ipaddress
import json
from collections.abc import Callable
from typing import Any

import pytest
import urllib3
from local_tls import HOST, NetworkAudit, Pki, TlsServer
from test_transport_urllib3_local_tls import (
    LOOPBACK,
    SECOND_LOOPBACK,
    Resolver,
    code_of,
    run,
    target,
)

from geo_connectors import egress_policy as ep
from geo_connectors import transport_urllib3 as tu

pytestmark = pytest.mark.usefixtures("allow_loopback_for_these_tests")

LIMITS = tu.ResponseHeaderLimits(max_count=10, max_name_bytes=20, max_value_bytes=50, max_total_bytes=300)


def transport_for(pki: Pki, server: TlsServer, path: str, resolver: Resolver | None = None, **kw: Any) -> Any:
    verified, req = target(HOST, server.port, path, resolver)
    return tu.Urllib3PinnedTransport(
        verified.destination, tu.verifying_context_factory(pki.ca_pem), **kw
    ), req


# ======================================================================================================
# 1. peer-address assertion
# ======================================================================================================
def test_a_matching_peer_succeeds_and_the_check_runs_on_the_real_tls_socket(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[type, object]] = []
    real = tu._peer_address

    def spy(sock: object) -> object:
        peer = real(sock)
        seen.append((type(sock), peer))
        return peer

    monkeypatch.setattr(tu, "_peer_address", spy)
    resolver = Resolver([LOOPBACK], [SECOND_LOOPBACK])
    t, req = transport_for(pki, server, "/ok", resolver)
    with NetworkAudit() as audit:
        res = t.execute(req)
    assert res.status == 200
    assert len(seen) == 1 and seen[0][0].__name__ == "SSLSocket" and seen[0][1] == (LOOPBACK, server.port)
    assert resolver.calls == [(HOST, server.port)]  # one resolution, during verification only
    assert server.recorder.sni == [HOST]  # the original hostname stayed the SNI name
    assert dict(server.recorder.last()["headers"])["Host"] == f"{HOST}:{server.port}"  # and the Host name
    assert all(
        ipaddress.ip_address(a[0][0]) in ipaddress.ip_network("127.0.0.0/8")
        for e, a in audit.events
        if e == "socket.connect"
    )
    assert not [1 for e, a in audit.events if e != "socket.connect" and HOST in map(str, a)]


def test_the_exact_selected_address_is_what_counts_not_any_validated_address(pki: Pki) -> None:
    with TlsServer(pki, HOST) as a, TlsServer(pki, HOST, ip=SECOND_LOOPBACK, port=a.port) as b:
        resolver = Resolver([LOOPBACK, SECOND_LOOPBACK])
        verified, req = target(HOST, a.port, "/ok", resolver)
        assert verified.destination.addresses == (LOOPBACK, SECOND_LOOPBACK)
        t = tu.Urllib3PinnedTransport(verified.destination, tu.verifying_context_factory(pki.ca_pem))
        assert t.execute(req).status == 200 and a.recorder.count() == 1 and b.recorder.count() == 0
        second = dataclasses.replace(
            req, connect_ip=SECOND_LOOPBACK
        )  # also a validated address, now selected
        assert t.execute(second).status == 200 and b.recorder.count() == 1
        assert resolver.calls == [(HOST, a.port)]


@pytest.mark.parametrize(
    "reported",
    [
        ("127.0.0.9", 0),  # a different address (port filled in below)
        ("::ffff:127.0.0.1", 0),  # IPv4-mapped spelling of the right address is NOT equality
        ("::1", 0),
        ("127.0.0.2", 0),  # another validated-looking loopback address
        ("127.0.0.1", -1),  # right address, wrong port
    ],
)
def test_a_mismatching_peer_fails_before_any_request_is_written(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch, reported: tuple[str, int]
) -> None:
    host, port = reported
    wrong_port = port != 0
    monkeypatch.setattr(
        tu, "_peer_address", lambda sock: (host, server.port + 1 if wrong_port else server.port)
    )
    resolver = Resolver([LOOPBACK], [SECOND_LOOPBACK])
    t, req = transport_for(pki, server, "/ok", resolver)
    assert code_of(lambda: t.execute(req)) == "transport_peer_mismatch"
    assert (
        server.recorder.count() == 0
    )  # no HTTP request reached the server, so no response body was possible
    assert server.recorder.sni == [HOST]  # the handshake used the original hostname as SNI
    assert resolver.calls == [(HOST, server.port)]  # and nothing resolved again


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "127.0.0.1",
        ("127.0.0.1",),
        (b"127.0.0.1", 1),
        ("127.0.0.1%lo", 1),
        ("fe80::1%eth0", 1, 0, 1),
        ("not-an-ip", 1),
        ("", 1),
        (127, 1),
        ("127.0.0.1", True),
        ("127.0.0.1", "443"),
        ["127.0.0.1", 1],
        ("127.0.0.1", 1, 2),
    ],
)
def test_a_malformed_peer_address_fails_closed(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    monkeypatch.setattr(tu, "_peer_address", lambda sock: bad)
    t, req = transport_for(pki, server, "/ok")
    assert code_of(lambda: t.execute(req)) == "transport_peer_malformed"
    assert server.recorder.count() == 0


def test_an_unavailable_peer_address_fails_closed(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(sock: object) -> object:
        raise OSError("not connected")

    monkeypatch.setattr(tu, "_peer_address", boom)
    t, req = transport_for(pki, server, "/ok")
    assert code_of(lambda: t.execute(req)) == "transport_peer_unavailable"
    assert server.recorder.count() == 0
    # the real reader on a missing socket or a socket without the accessor is also "unavailable"
    monkeypatch.undo()
    for no_sock in (None, object(), 5):
        with pytest.raises(tu.TransportError) as e:
            tu.assert_peer(no_sock, LOOPBACK, 443)
        assert e.value.code == "transport_peer_unavailable"


def test_a_peer_failure_closes_the_connection_and_the_pool(
    pki: Pki, server: TlsServer, monkeypatch: Any
) -> None:
    class Spy(urllib3.HTTPSConnectionPool):
        made: list[Spy] = []  # noqa: RUF012

        def __init__(self, *a: Any, **k: Any) -> None:
            super().__init__(*a, **k)
            Spy.made.append(self)

    monkeypatch.setattr(tu, "HTTPSConnectionPool", Spy)
    monkeypatch.setattr(tu, "_peer_address", lambda sock: ("127.0.0.9", server.port))
    t, req = transport_for(pki, server, "/ok")
    assert code_of(lambda: t.execute(req)) == "transport_peer_mismatch"
    assert len(Spy.made) == 1 and Spy.made[0].pool is None
    assert Spy.made[0].ConnectionCls.__name__ == "_PeerCheckedHTTPSConnection"
    assert Spy.made[0].conn_kw["expected_peer_ip"] == LOOPBACK  # the SELECTED, validated address
    assert Spy.made[0].conn_kw["expected_peer_port"] == server.port


def test_a_connection_whose_peer_fails_the_check_is_closed_by_connect_itself(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Independent of the pool's own clean-up: after a failed assertion the socket must already be closed."""
    monkeypatch.setattr(tu, "_peer_address", lambda sock: ("127.0.0.9", server.port))
    conn = tu._PeerCheckedHTTPSConnection(
        host=LOOPBACK,
        port=server.port,
        server_hostname=HOST,
        assert_hostname=HOST,
        ssl_context=tu.verifying_context_factory(pki.ca_pem)(),
        cert_reqs="CERT_REQUIRED",
        expected_peer_ip=LOOPBACK,
        expected_peer_port=server.port,
    )
    with pytest.raises(tu.TransportError) as e:
        conn.connect()
    assert e.value.code == "transport_peer_mismatch"
    assert conn.sock is None and conn.is_closed
    assert server.recorder.count() == 0


def test_the_peer_assertion_unit_accepts_only_exact_equality() -> None:
    class FakeSock:
        def __init__(self, peer: object) -> None:
            self.peer = peer

        def getpeername(self) -> object:
            return self.peer

    ok = [("127.0.0.1", 443), ("127.0.0.1", 443, 0, 0), ("::1", 443, 0, 0)]
    tu.assert_peer(FakeSock(ok[0]), "127.0.0.1", 443)
    tu.assert_peer(FakeSock(ok[1]), "127.0.0.1", 443)  # AF_INET6-style 4-tuple shape
    tu.assert_peer(FakeSock(ok[2]), "::1", 443)
    tu.assert_peer(FakeSock(("0:0:0:0:0:0:0:1", 443, 0, 0)), "::1", 443)  # same address, other spelling
    for peer, expected, port in (
        (("127.0.0.2", 443), "127.0.0.1", 443),
        (("127.0.0.1", 444), "127.0.0.1", 443),
        (("::ffff:127.0.0.1", 443, 0, 0), "127.0.0.1", 443),
    ):
        with pytest.raises(tu.TransportError) as e:
            tu.assert_peer(FakeSock(peer), expected, port)
        assert e.value.code == "transport_peer_mismatch"


# ======================================================================================================
# 2. response-header policy
# ======================================================================================================
def test_ordinary_minimal_json_api_headers_succeed_under_the_default_limits(
    pki: Pki, server: TlsServer
) -> None:
    res = run(pki, server, "/stac-like")
    assert res.status == 200
    assert json.loads(res.body)["type"] == "FeatureCollection"
    assert dict(res.headers)["content-type"] == "application/geo+json"
    res2 = run(pki, server, "/ok")  # and the smallest response
    assert res2.status == 200


def raw(kind: str, **q: object) -> str:
    return "/raw?" + "&".join(f"{k}={v}" for k, v in {"kind": kind, **q}.items())


# every /raw answer carries 3 base fields: Content-Type (12+16+4=32 bytes), Content-Length (14+1+4=19) and
# Connection (10+5+4=19) => 70 bytes
@pytest.mark.parametrize(
    ("path_ok", "path_bad", "code"),
    [
        (raw("count", n=7), raw("count", n=8), "transport_header_count"),  # 3 + n == max_count (10) / 11
        (raw("name", n=20), raw("name", n=21), "transport_header_name_size"),
        (raw("value", n=50), raw("value", n=51), "transport_header_value_size"),
        # 4 fields of 6 + 40 + 4 = 50 bytes plus the base 70 = 270 <= 300; a 5th makes 320 > 300
        (raw("total", n=4, size=40), raw("total", n=5, size=40), "transport_header_total_size"),
    ],
)
def test_each_limit_accepts_the_boundary_and_rejects_one_over(
    pki: Pki, server: TlsServer, path_ok: str, path_bad: str, code: str
) -> None:
    assert run(pki, server, path_ok, header_limits=LIMITS).body == b"{}"
    with pytest.raises(tu.TransportError) as e:
        run(pki, server, path_bad, header_limits=LIMITS)
    assert e.value.code == code
    assert not isinstance(e.value, tu.TransportStatusError)
    assert "{}" not in str(e.value)  # nothing from the response is echoed back


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (
            "bad-name",
            "transport_header_malformed",
        ),  # `Bad(Name)` is accepted by the stdlib parser, not a token
        ("ctrl-value", "transport_header_malformed"),
        ("dup-ct", "transport_header_duplicate"),
        ("dup-cl-same", "transport_header_duplicate"),
        ("dup-loc", "transport_header_duplicate"),
        ("te-and-cl", "transport_header_conflict"),
    ],
)
def test_malformed_and_duplicate_sensitive_headers_are_rejected_with_their_own_code(
    pki: Pki, server: TlsServer, kind: str, code: str
) -> None:
    assert code_of(lambda: run(pki, server, raw(kind))) == code


def test_the_limits_are_checked_before_content_encoding_location_and_status(
    pki: Pki, server: TlsServer
) -> None:
    # over-limit AND gzip: the header code wins, the content-encoding rule never runs
    assert code_of(lambda: run(pki, server, raw("count", n=9, enc=1), header_limits=LIMITS)) == (
        "transport_header_count"
    )
    # over-limit AND a 302 with Location: a header error, not a TransportStatusError carrying the Location
    with pytest.raises(tu.TransportError) as e:
        run(pki, server, raw("count", n=9, status=302, loc=1), header_limits=LIMITS)
    assert e.value.code == "transport_header_count" and not isinstance(e.value, tu.TransportStatusError)
    # the same response within limits does reach the redirect handling
    with pytest.raises(tu.TransportStatusError) as s:
        run(pki, server, raw("plain", status=302, loc=1), header_limits=LIMITS)
    assert ep.redirect_location(s.value.response) == "https://other.test.example/x"
    # and within limits the gzip rule applies as before
    assert code_of(lambda: run(pki, server, raw("plain", enc=1), header_limits=LIMITS)) == (
        "transport_content_encoding"
    )


def test_no_body_byte_is_read_when_the_headers_are_refused(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[int] = []
    original = urllib3.response.HTTPResponse.read1

    def counting(self: Any, *a: Any, **k: Any) -> bytes:
        reads.append(1)
        return original(self, *a, **k)

    monkeypatch.setattr(urllib3.response.HTTPResponse, "read1", counting)
    assert (
        code_of(lambda: run(pki, server, raw("count", n=9), header_limits=LIMITS)) == "transport_header_count"
    )
    assert reads == []
    assert run(pki, server, raw("count", n=7), header_limits=LIMITS).body == b"{}"
    assert reads  # the control: an accepted response is read


def test_the_pool_is_closed_when_the_headers_are_refused(
    pki: Pki, server: TlsServer, monkeypatch: Any
) -> None:
    pools: list[Any] = []

    class Spy(urllib3.HTTPSConnectionPool):
        def __init__(self, *a: Any, **k: Any) -> None:
            super().__init__(*a, **k)
            pools.append(self)

    monkeypatch.setattr(tu, "HTTPSConnectionPool", Spy)
    assert (
        code_of(lambda: run(pki, server, raw("count", n=9), header_limits=LIMITS)) == "transport_header_count"
    )
    assert pools[0].pool is None


def test_the_checker_works_on_raw_lines_and_counts_duplicates_that_a_dict_would_merge() -> None:
    tu.check_response_headers([("A", "1"), ("B", "2")], LIMITS)
    with pytest.raises(
        tu.TransportError
    ) as e:  # identical pairs must still count (a set/dict view would drop one)
        tu.check_response_headers([("X", "1")] * 11, LIMITS)
    assert e.value.code == "transport_header_count"
    with pytest.raises(tu.TransportError) as d:
        tu.check_response_headers([("Content-Length", "2"), ("content-length", "2")], LIMITS)
    assert d.value.code == "transport_header_duplicate"
    tu.check_response_headers(
        [("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")], LIMITS
    )  # repeating is normal here
    with pytest.raises(tu.TransportError) as c:
        tu.check_response_headers([("Content-Length", "2"), ("Transfer-Encoding", "chunked")], LIMITS)
    assert c.value.code == "transport_header_conflict"
    for bad in ([(1, "x")], [("x", 1)], [("x", "Ā")]):
        with pytest.raises(tu.TransportError) as m:
            tu.check_response_headers(bad, LIMITS)  # type: ignore[arg-type]
        assert m.value.code == "transport_header_malformed"
    tu.check_response_headers([("X", "a\tb")], LIMITS)  # HTAB is allowed inside a value


@pytest.mark.parametrize(
    "field",
    ["max_count", "max_name_bytes", "max_value_bytes", "max_total_bytes"],
)
def test_invalid_header_limits_are_refused(field: str) -> None:
    ceilings = {
        "max_count": tu.HEADER_COUNT_CEILING,
        "max_name_bytes": tu.HEADER_NAME_CEILING,
        "max_value_bytes": tu.HEADER_VALUE_CEILING,
        "max_total_bytes": tu.HEADER_TOTAL_CEILING,
    }
    tu.ResponseHeaderLimits(**{field: ceilings[field]})  # the ceiling itself is allowed
    for bad in (0, -1, ceilings[field] + 1, 1.5, True, None, "5"):
        with pytest.raises(tu.TransportError) as e:
            tu.ResponseHeaderLimits(**{field: bad})  # type: ignore[arg-type]
        assert e.value.code == "transport_config"


def test_defaults_are_within_the_ceilings_and_fit_ordinary_responses() -> None:
    d = tu.DEFAULT_HEADER_LIMITS
    assert (d.max_count, d.max_name_bytes, d.max_value_bytes, d.max_total_bytes) == (32, 64, 4096, 16384)
    assert d.max_count <= tu.HEADER_COUNT_CEILING and d.max_total_bytes <= tu.HEADER_TOTAL_CEILING


def test_a_non_limits_object_is_refused_by_the_constructor(pki: Pki, server: TlsServer) -> None:
    verified, _ = target(HOST, server.port, "/ok")
    with pytest.raises(tu.TransportError) as e:
        tu.Urllib3PinnedTransport(
            verified.destination,
            tu.verifying_context_factory(pki.ca_pem),
            header_limits={"max_count": 99},  # type: ignore[arg-type]
        )
    assert e.value.code == "transport_config"


# ---- limits owned by the Python HTTP stack: rejected safely, but the limit and the exception are not ours --------
@pytest.mark.parametrize(
    "path",
    [
        raw("count", n=150),  # more than the stdlib's 100 header fields
        raw("value", n=70000),  # a header line longer than the stdlib's 65536 bytes
    ],
)
def test_stdlib_owned_limits_still_end_in_a_safe_refusal(pki: Pki, server: TlsServer, path: str) -> None:
    with pytest.raises(tu.TransportError) as e:
        run(pki, server, path, header_limits=tu.ResponseHeaderLimits(max_count=100, max_value_bytes=8192))
    assert (
        e.value.code == "transport_protocol"
    )  # urllib3 maps the stdlib's LineTooLong / HTTPException to this
    assert not e.value.code.startswith("transport_header_")  # these never reach the adapter's own checks


def test_differing_content_length_lines_are_refused_by_urllib3_before_the_adapter(
    pki: Pki, server: TlsServer
) -> None:
    with pytest.raises(tu.TransportError) as e:
        run(pki, server, raw("dup-cl-diff"))
    assert e.value.code == "transport_error"  # urllib3's InvalidHeader, raised inside urlopen


# ---- everything above stayed on loopback --------------------------------------------------------------------
def test_the_audit_hook_saw_only_loopback_connections_and_no_name_resolution_for_the_logical_host(
    pki: Pki, server: TlsServer
) -> None:
    calls: list[Callable[[], object]] = [
        lambda: run(pki, server, "/stac-like"),
        lambda: run(pki, server, raw("count", n=9), header_limits=LIMITS),
        lambda: run(pki, server, raw("dup-ct")),
    ]
    with NetworkAudit() as audit:
        for fn in calls:
            try:
                fn()
            except tu.TransportError:
                pass
    connects = [a[0] for e, a in audit.events if e == "socket.connect"]
    assert len(connects) >= 3
    for ip, port in connects:
        assert ipaddress.ip_address(ip) in ipaddress.ip_network("127.0.0.0/8") and port == server.port
    for event, args in audit.events:
        if event != "socket.connect":
            assert event == "socket.getaddrinfo" and args[0] == LOOPBACK, (
                event,
                args,
            )  # numeric literal only
            assert HOST not in map(str, args)
