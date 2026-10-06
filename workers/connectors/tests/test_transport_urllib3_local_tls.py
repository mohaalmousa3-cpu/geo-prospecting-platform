"""Local TLS proof of the urllib3 transport adapter (Phase 3b R8). Loopback only; no DNS; no provider.

The offline policy still refuses loopback addresses (R-b). To exercise a real socket, ONE helper below patches the
policy's address classifier for 127.0.0.0/8 *inside these tests only*; every other step (URL parsing, exact
allow-list, single injected resolution, immutable VerifiedDestination, PinnedRequest planning) is the real code.
"""

from __future__ import annotations

import dataclasses
import ipaddress
import os
import ssl
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import urllib3
from local_tls import (
    HOST,
    OTHER_HOST,
    NetworkAudit,
    Pki,
    TlsServer,
    unused_loopback_port,
)

from geo_connectors import egress_policy as ep
from geo_connectors import fixed_query
from geo_connectors import transport_urllib3 as tu
from geo_connectors.egress_policy import (
    EgressAllowlist,
    PinnedRequest,
    RequestBudget,
    VerifiedUrl,
    plan_pinned_request,
    verify_url,
)

LOOPBACK = "127.0.0.1"
SECOND_LOOPBACK = "127.0.0.2"


pytestmark = pytest.mark.usefixtures("allow_loopback_for_these_tests")


class Resolver:
    def __init__(self, *answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append((host, port))
        return self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]


def budget(**kw: Any) -> RequestBudget:
    base: dict[str, Any] = {
        "max_requests": 5,
        "connect_timeout_s": 2,
        "read_timeout_s": 2,
        "total_timeout_s": 10,
        "max_response_bytes": 1000,
    }
    base.update(kw)
    return RequestBudget(**base)


def target(
    host: str, port: int, path: str, resolver: Resolver | None = None, b: RequestBudget | None = None
) -> tuple[VerifiedUrl, PinnedRequest]:
    resolver = resolver or Resolver([LOOPBACK])
    verified = verify_url(f"https://{host}:{port}{path}", EgressAllowlist.of([(host, port)]), resolver)
    return verified, plan_pinned_request(verified, b or budget(), requests_made=0)


def run(
    pki: Pki,
    server: TlsServer,
    path: str,
    *,
    host: str = HOST,
    b: RequestBudget | None = None,
    clock: Callable[[], float] | None = None,
    cafile: str | None = None,
    header_limits: tu.ResponseHeaderLimits | None = None,
) -> ep.TransportResponse:
    verified, req = target(host, server.port, path, b=b)
    t = tu.Urllib3PinnedTransport(
        verified.destination,
        tu.verifying_context_factory(cafile or pki.ca_pem),
        **({"clock": clock} if clock else {}),
        header_limits=header_limits,
    )
    return t.execute(req)


def code_of(fn: Callable[[], object]) -> str:
    with pytest.raises(tu.TransportError) as e:
        fn()
    return e.value.code


# ---- the intended connection: pinned IP, Host, SNI, verification against the logical name ------------------------
def test_connects_to_the_given_ip_with_intended_host_sni_and_verifies_the_logical_name(
    pki: Pki, server: TlsServer
) -> None:
    resolver = Resolver([LOOPBACK], [SECOND_LOOPBACK])
    verified, req = target(HOST, server.port, "/ok", resolver)
    assert verified.destination.addresses == (LOOPBACK,) and verified.destination.tls_server_hostname == HOST
    with NetworkAudit() as audit:
        res = tu.Urllib3PinnedTransport(
            verified.destination, tu.verifying_context_factory(pki.ca_pem)
        ).execute(req)
    assert (res.status, res.body) == (200, b'{"ok": true}')
    assert dict(res.headers) == {"content-type": "application/json", "content-length": "12"}
    # the server saw exactly one request, the intended SNI and the intended Host header
    assert server.recorder.count() == 1 and server.recorder.sni == [HOST]
    seen = server.recorder.last()
    assert dict(seen["headers"])["Host"] == f"{HOST}:{server.port}"
    assert seen["server_ip"] == LOOPBACK
    # network events of this thread: loopback connects only, and the logical name was never resolved
    kinds = [e for e, _ in audit.events]
    assert "socket.connect" in kinds
    for event, args in audit.events:
        if event == "socket.connect":
            assert ipaddress.ip_address(args[0][0]) in ipaddress.ip_network("127.0.0.0/8"), args
        else:
            assert HOST not in map(str, args), (event, args)
            assert event == "socket.getaddrinfo" and args[0] == LOOPBACK, (
                event,
                args,
            )  # numeric literal only
    assert resolver.calls == [(HOST, server.port)]  # the injected resolver ran once, during verification


def test_only_the_expected_request_headers_are_sent_and_no_cookie_jar_exists(
    pki: Pki, server: TlsServer
) -> None:
    run(pki, server, "/ok")
    run(pki, server, "/ok")  # the first answer carried Set-Cookie
    for r in server.recorder.requests:
        names = {k.lower() for k, _ in r["headers"]}
        assert names == {"host", "accept-encoding", "user-agent"}, names
        h = dict(r["headers"])
        assert h["Accept-Encoding"] == "identity" and h["User-Agent"] == tu.USER_AGENT


def test_a_second_resolver_answer_is_irrelevant_after_verification(pki: Pki) -> None:
    with TlsServer(pki, HOST) as a:
        with TlsServer(pki, HOST, ip=SECOND_LOOPBACK, port=a.port) as b:  # same port on 127.0.0.2
            resolver = Resolver([LOOPBACK], [SECOND_LOOPBACK], [SECOND_LOOPBACK])
            verified, req = target(HOST, a.port, "/ok", resolver)
            t = tu.Urllib3PinnedTransport(verified.destination, tu.verifying_context_factory(pki.ca_pem))
            for _ in range(3):
                assert t.execute(req).status == 200
            assert resolver.calls == [(HOST, a.port)]  # never consulted again
            assert a.recorder.count() == 3 and b.recorder.count() == 0


def test_a_certificate_for_another_hostname_fails_verification(pki: Pki) -> None:
    with TlsServer(pki, OTHER_HOST) as wrong:
        # the server's certificate is valid for OTHER_HOST under the trusted CA, but we expect HOST
        assert code_of(lambda: run(pki, wrong, "/ok", host=HOST)) == "transport_tls"
        assert wrong.recorder.count() == 0  # the TLS handshake never completed an HTTP exchange
        # control: the same server and CA succeed when the logical name matches its certificate
        assert run(pki, wrong, "/ok", host=OTHER_HOST).status == 200


def test_an_untrusted_ca_fails_with_the_system_store_and_the_system_bundle_is_present(
    pki: Pki, server: TlsServer
) -> None:
    ctx = tu.verifying_context_factory(None)()
    stats = ctx.cert_store_stats()
    assert Path("/etc/ssl/certs/ca-certificates.crt").is_file()
    assert stats["x509_ca"] > 0  # the system store loads; it simply does not contain the private test CA
    verified, req = target(HOST, server.port, "/ok")
    t = tu.Urllib3PinnedTransport(verified.destination, tu.verifying_context_factory(None))
    assert code_of(lambda: t.execute(req)) == "transport_tls"


# ---- redirects, retries, status, encoding ---------------------------------------------------------------------
def test_a_redirect_is_returned_not_followed_and_needs_independent_validation(
    pki: Pki, server: TlsServer
) -> None:
    with pytest.raises(tu.TransportStatusError) as e:
        run(pki, server, "/redirect")
    assert e.value.status == 302
    assert server.recorder.count() == 1  # nothing was followed
    assert ep.redirect_location(e.value.response) == f"https://{OTHER_HOST}/x"
    assert e.value.response.body == b"" and "REDIRECT-BODY" not in repr(e.value) + str(e.value)
    resolver = Resolver([LOOPBACK])
    c = code_of  # redirect validation is a separate, full validation; with redirects disabled it refuses outright
    with pytest.raises(ep.EgressPolicyError) as p:
        ep.validate_redirect(
            ep.redirect_location(e.value.response),
            allowlist=EgressAllowlist.of([(HOST, server.port)]),
            resolver=resolver,
            budget=budget(),
            redirects_followed=0,
        )
    assert p.value.code == "redirects_disabled" and resolver.calls == [] and c is code_of


def test_retries_are_absent_and_the_test_is_sensitive_to_them(pki: Pki, server: TlsServer) -> None:
    assert code_of(lambda: run(pki, server, "/reset")) == "transport_protocol"
    assert server.recorder.count("/reset") == 1
    # sensitivity control: the same endpoint through a pool with urllib3's default Retry(3) is requested repeatedly
    with TlsServer(pki, HOST) as other:
        pool = urllib3.HTTPSConnectionPool(
            LOOPBACK, other.port, server_hostname=HOST, assert_hostname=HOST, ca_certs=pki.ca_pem, timeout=2
        )
        try:
            with pytest.raises(urllib3.exceptions.HTTPError):
                pool.urlopen("GET", "/reset", headers={"Host": HOST}, assert_same_host=False, redirect=False)
        finally:
            pool.close()
        assert other.recorder.count("/reset") > 1


@pytest.mark.parametrize("path", ["/status500", "/status404"])
def test_non_2xx_statuses_are_refused_and_no_body_is_exposed(pki: Pki, server: TlsServer, path: str) -> None:
    with pytest.raises(tu.TransportStatusError) as e:
        run(pki, server, path)
    err = e.value
    assert err.status in (404, 500) and err.response.body == b"" and err.response.headers == ()
    assert "SECRETBODY" not in str(err) + repr(err) + repr(err.response)
    assert server.recorder.count() == 1


def test_a_2xx_without_a_body_is_accepted(pki: Pki, server: TlsServer) -> None:
    res = run(pki, server, "/empty")
    assert (res.status, res.body) == (204, b"")


def test_an_unexpected_content_encoding_is_rejected_and_identity_is_accepted(
    pki: Pki, server: TlsServer
) -> None:
    assert code_of(lambda: run(pki, server, "/gzip")) == "transport_content_encoding"
    res = run(pki, server, "/identity")
    assert res.body == b"plain"  # nothing is ever decompressed


# ---- byte and time budgets -------------------------------------------------------------------------------------
def test_the_byte_ceiling_stops_processing(pki: Pki, server: TlsServer) -> None:
    assert run(pki, server, "/big?n=1000").body == b"x" * 1000  # exactly the ceiling is allowed
    assert code_of(lambda: run(pki, server, "/big?n=1001")) == "transport_too_large"  # declared length
    # without Content-Length the ceiling is enforced while streaming
    assert code_of(lambda: run(pki, server, "/stream-nolen")) == "transport_too_large"


def test_the_deadline_is_checked_before_the_request(pki: Pki, server: TlsServer) -> None:
    ticks = iter([0.0, 100.0, 200.0, 300.0])
    assert code_of(
        lambda: run(pki, server, "/ok", b=budget(total_timeout_s=5), clock=lambda: next(ticks))
    ) == ("transport_deadline")
    assert server.recorder.count() == 0  # nothing was sent


@pytest.mark.timeout(20)
def test_the_deadline_is_checked_during_body_reads_with_a_fake_clock(pki: Pki) -> None:
    big = budget(total_timeout_s=25, max_response_bytes=100000)
    state = {"t": 0.0}

    def clock() -> float:
        state["t"] += 10.0  # every check "takes" ten seconds
        return state["t"]

    with TlsServer(pki, HOST) as s:
        assert code_of(lambda: run(pki, s, "/big?n=60000", b=big, clock=clock)) == "transport_deadline"
        assert s.recorder.count() == 1  # the request was made; the body loop was cut off by the deadline


@pytest.mark.timeout(20)
def test_a_slow_drip_cannot_outlive_the_real_deadline(pki: Pki, server: TlsServer) -> None:
    b = budget(total_timeout_s=1, connect_timeout_s=1, read_timeout_s=1, max_response_bytes=100000)
    start = time.monotonic()
    assert code_of(lambda: run(pki, server, "/drip", b=b)) == "transport_deadline"
    assert time.monotonic() - start < 3  # deadline plus at most one read timeout, not the 100 s of the drip


@pytest.mark.timeout(20)
def test_a_read_timeout_is_bounded(pki: Pki, server: TlsServer) -> None:
    start = time.monotonic()
    assert code_of(lambda: run(pki, server, "/hang", b=budget(read_timeout_s=0.3, total_timeout_s=5))) == (
        "transport_timeout"
    )
    assert time.monotonic() - start < 3


def test_a_refused_connection_is_reported_as_a_connect_failure(pki: Pki) -> None:
    port = unused_loopback_port()
    verified, req = target(HOST, port, "/ok")
    t = tu.Urllib3PinnedTransport(verified.destination, tu.verifying_context_factory(pki.ca_pem))
    assert code_of(lambda: t.execute(req)) == "transport_connect"


# ---- environment and configuration ---------------------------------------------------------------------------
def test_environment_proxies_and_key_logging_are_ignored(
    pki: Pki, server: TlsServer, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dead = unused_loopback_port()
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(var, f"http://127.0.0.1:{dead}")
    keylog = tmp_path / "keys.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "does-not-exist.pem"))
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert run(pki, server, "/ok").status == 200  # went straight to the pinned IP, not through the proxy
    assert server.recorder.count() == 1
    assert not keylog.exists()  # our context never touched the key-log variable
    # control: the stdlib helper we deliberately avoid DOES honour it and creates the file
    ssl.create_default_context(cafile=pki.ca_pem)
    assert keylog.exists() and os.environ["SSLKEYLOGFILE"] == str(keylog)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_the_context_must_verify_and_is_not_left_weaker(pki: Pki, server: TlsServer) -> None:
    verified, req = target(HOST, server.port, "/ok")

    def none_ctx() -> ssl.SSLContext:
        c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c

    def nohost_ctx() -> ssl.SSLContext:
        c = ssl.create_default_context(cafile=pki.ca_pem)
        c.check_hostname = False
        return c

    def old_tls() -> ssl.SSLContext:
        c = ssl.create_default_context(cafile=pki.ca_pem)
        c.minimum_version = ssl.TLSVersion.TLSv1
        return c

    for bad in (none_ctx, nohost_ctx, old_tls, lambda: "not a context"):  # type: ignore[return-value]
        t = tu.Urllib3PinnedTransport(verified.destination, bad)
        assert code_of(lambda t=t: t.execute(req)) == "transport_tls_config"  # type: ignore[misc]
    assert server.recorder.count() == 0


class SpyPool(urllib3.HTTPSConnectionPool):
    instances: list[SpyPool] = []  # noqa: RUF012
    last_kwargs: dict[str, Any] = {}  # noqa: RUF012
    urlopen_kwargs: dict[str, Any] = {}  # noqa: RUF012
    responses: list[Any] = []  # noqa: RUF012

    def __init__(self, *a: Any, **kw: Any) -> None:
        SpyPool.last_kwargs = dict(kw, _args=a)
        SpyPool.instances.append(self)
        super().__init__(*a, **kw)

    def urlopen(self, method: str, url: str, **kw: Any) -> Any:  # type: ignore[override]
        SpyPool.urlopen_kwargs = dict(kw, _method=method, _url=url)
        resp = super().urlopen(method, url, **kw)
        SpyPool.responses.append(resp)
        return resp


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> type[SpyPool]:
    SpyPool.instances, SpyPool.responses = [], []
    monkeypatch.setattr(tu, "HTTPSConnectionPool", SpyPool)
    return SpyPool


def test_the_pool_and_request_arguments_are_exactly_the_hardened_ones(
    pki: Pki, server: TlsServer, spy: type[SpyPool]
) -> None:
    run(pki, server, "/ok", b=budget(connect_timeout_s=1.5, read_timeout_s=2.5, total_timeout_s=30))
    k, u = spy.last_kwargs, spy.urlopen_kwargs
    assert k["host"] == LOOPBACK and k["port"] == server.port and k["maxsize"] == 1 and k["block"] is True
    assert k["server_hostname"] == HOST and k["assert_hostname"] == HOST  # SNI and verification name
    assert k["cert_reqs"] == "CERT_REQUIRED" and k["retries"] is False
    ctx = k["ssl_context"]
    assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_REQUIRED
    assert u["retries"] is False and u["redirect"] is False and u["assert_same_host"] is False
    assert u["preload_content"] is False and u["decode_content"] is False
    assert set(u["headers"]) == {"Host", "Accept-Encoding", "User-Agent"}
    assert u["headers"]["Host"] == f"{HOST}:{server.port}" and u["headers"]["Accept-Encoding"] == "identity"
    assert u["_method"] == "GET" and u["_url"] == "/ok"
    assert (u["timeout"].connect_timeout, u["timeout"].read_timeout) == (1.5, 2.5)
    assert u["pool_timeout"] == 2  # ceil(1.5): urlopen types it as an int (the one-use pool never contends)
    assert k["timeout"].connect_timeout == 1.5 and k["timeout"].read_timeout == 2.5


@pytest.mark.parametrize(
    "path", ["/ok", "/status500", "/redirect", "/gzip", "/big?n=5000", "/reset", "/stream-nolen"]
)
def test_every_pool_and_response_is_closed_on_success_and_on_every_failure(
    pki: Pki, server: TlsServer, spy: type[SpyPool], path: str
) -> None:
    try:
        run(pki, server, path)
    except tu.TransportError:
        pass
    assert len(spy.instances) == 1
    assert spy.instances[0].pool is None  # HTTPConnectionPool.close() empties and drops the pool
    for resp in spy.responses:
        assert resp.closed or resp.connection is None


def test_tls_failures_also_close_the_pool(pki: Pki, spy: type[SpyPool]) -> None:
    with TlsServer(pki, OTHER_HOST) as wrong:
        assert code_of(lambda: run(pki, wrong, "/ok", host=HOST)) == "transport_tls"
    assert spy.instances[0].pool is None


# ---- inputs: only verified objects; inconsistent requests never reach a socket ----------------------------------
def test_only_a_verified_destination_and_a_consistent_pinned_request_are_accepted(
    pki: Pki, server: TlsServer
) -> None:
    verified, req = target(HOST, server.port, "/ok")
    factory = tu.verifying_context_factory(pki.ca_pem)
    for not_dest in (f"https://{HOST}:{server.port}/ok", ("127.0.0.1", server.port), None, object()):
        with pytest.raises(tu.TransportError) as e:
            tu.Urllib3PinnedTransport(not_dest, factory)  # type: ignore[arg-type]
        assert e.value.code == "transport_mismatch"
    with pytest.raises(tu.TransportError):
        tu.Urllib3PinnedTransport(verified.destination, "not callable")  # type: ignore[arg-type]
    t = tu.Urllib3PinnedTransport(verified.destination, factory)
    forged: list[Any] = [
        f"https://{HOST}:{server.port}/ok",
        {"path": "/ok"},
        dataclasses.replace(req, connect_ip="127.0.0.9"),  # not a verified address
        dataclasses.replace(req, connect_ip="8.8.8.8"),
        dataclasses.replace(req, port=server.port + 1),
        dataclasses.replace(req, server_hostname=OTHER_HOST),
        dataclasses.replace(req, host_header="evil.example"),
        dataclasses.replace(req, method="POST"),
        dataclasses.replace(req, path_and_query="https://evil.example/ok"),
        dataclasses.replace(req, path_and_query="//evil.example/ok"),
        dataclasses.replace(req, path_and_query="/a b"),
        dataclasses.replace(req, budget="no budget"),  # type: ignore[arg-type]
    ]
    for bad in forged:
        with NetworkAudit() as audit:
            assert code_of(lambda bad=bad: t.execute(bad)) == "transport_mismatch"  # type: ignore[misc]
        assert audit.events == []  # refused before any socket activity
    assert server.recorder.count() == 0


def test_the_transport_signature_exposes_no_header_url_or_credential_parameter() -> None:
    import inspect

    assert list(inspect.signature(tu.Urllib3PinnedTransport.execute).parameters) == ["self", "request"]
    assert list(inspect.signature(tu.Urllib3PinnedTransport.__init__).parameters) == [
        "self", "destination", "ssl_context_factory", "clock", "header_limits",
    ]  # fmt: skip
    assert fixed_query.APPROVED_FOR_EXECUTION is False  # untouched by this checkpoint
