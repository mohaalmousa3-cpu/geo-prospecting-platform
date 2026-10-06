"""Phase 3b R8: urllib3 transport PROOF OF CONCEPT. Local test use only; unregistered and unreachable.

This module is the only place in the repository that imports an HTTP client (`urllib3==2.8.0`, approved by
the owner on 2026-10-06 as the *evaluated* transport only) and `ssl`. It is NOT imported by the registry,
the handler, the API, the runner or any job path (`tests/unit/test_architecture.py` and
`test_transport_urllib3_isolation.py` enforce it), no provider host or port is configured, and nothing here
approves a live request.

It consumes only objects produced by the offline policy (`egress_policy`):

* a `VerifiedDestination` (built only by `verify_url`, which resolved the name once and validated every
  address),
* a `PinnedRequest` (built by `plan_pinned_request`).

No URL string and no header from a caller can enter. The adapter cross-checks the request against the
destination (address, port, TLS name, Host header, method, path) and refuses anything inconsistent.

Connection: one `urllib3.HTTPSConnectionPool` per request, aimed at the validated IP, with `server_hostname`
(SNI), `assert_hostname` and the HTTP `Host` header all set to the original hostname (the documented urllib3
"Custom SNI Hostname" pattern, which also requires `assert_same_host=False`; redirects and retries are off
so that setting cannot lead anywhere else). The pool is created, used and closed inside `execute` (no shared
pool).

TLS: an explicit `ssl.SSLContext` from an injected factory, with `CERT_REQUIRED` and `check_hostname` on at
creation. NOTE (urllib3 2.8.0 behaviour, read in the source): when `assert_hostname` is given, urllib3
switches the context's `check_hostname` off and performs the hostname match itself (`_match_hostname`) after
the handshake, so each call gets a fresh context from the factory and the hostname check is urllib3's, not
the stdlib's. The tests prove a certificate for another name is refused.

Response: `Accept-Encoding: identity`, any other `Content-Encoding` refused, `decode_content=False` (nothing
is ever decompressed), a raw byte ceiling enforced while streaming, a monotonic total deadline checked
before the request and before every body read, and non-2xx statuses refused without reading the body.

Known limit: a body read can block for at most the read timeout, so the real total can exceed the deadline
by up to one read timeout. Not proven here: behaviour against a real provider, real DNS, proxies in the
network path.
"""

from __future__ import annotations

import math
import ssl
import time
from collections.abc import Callable

import urllib3.exceptions
from urllib3 import HTTPSConnectionPool, Timeout

from geo_connectors.egress_policy import (
    HTTPS_DEFAULT_PORT,
    EgressPolicyError,
    PinnedRequest,
    RequestBudget,
    TransportResponse,
    VerifiedDestination,
    ensure_relative_path,
)
from geo_connectors.errors import ConnectorError

CHUNK_BYTES = 16 * 1024
USER_AGENT = "geo-connectors-r8-poc"  # fixed placeholder; the real value is an owner decision (R3)
MAX_EXPOSED_HEADER_CHARS = 256
MAX_LOCATION_CHARS = 2048
_EXPOSED_HEADERS = ("content-type", "content-length")


class TransportError(ConnectorError):
    """A transport-level refusal or failure. `code` is stable; messages never contain response data."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TransportStatusError(TransportError):
    """A non-2xx status: only the status and, for a redirect, a bounded `Location` (never followed)."""

    def __init__(self, status: int, response: TransportResponse) -> None:
        super().__init__("transport_status", f"unexpected HTTP status {status}")
        self.status = status
        self.response = response  # empty body; headers: only a bounded Location for 3xx


def _fail(code: str, message: str) -> TransportError:
    return TransportError(code, message)


def verifying_context_factory(cafile: str | None = None) -> Callable[[], ssl.SSLContext]:
    """A factory of fresh, verifying contexts; no third-party CA bundle is involved.

    The context is built directly, NOT with `ssl.create_default_context()`: that helper reads the
    `SSLKEYLOGFILE` environment variable and would start writing TLS secrets to it (proved in the tests).
    With a `cafile` only that file is trusted. With none, the system store is loaded through OpenSSL's
    default paths, which OpenSSL itself may redirect via `SSL_CERT_FILE`/`SSL_CERT_DIR`: an explicit
    `cafile` is therefore the safer production choice."""

    def make() -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.check_hostname = True
        if cafile is None:
            ctx.load_default_certs()
        else:
            ctx.load_verify_locations(cafile=cafile)
        return ctx

    return make


def _checked_context(factory: Callable[[], ssl.SSLContext]) -> ssl.SSLContext:
    ctx = factory()
    if (
        not isinstance(ctx, ssl.SSLContext)
        or ctx.verify_mode != ssl.CERT_REQUIRED
        or not ctx.check_hostname
        or ctx.minimum_version < ssl.TLSVersion.TLSv1_2
    ):
        raise _fail(
            "transport_tls_config", "the SSL context must verify certificates and hostnames, TLS >= 1.2"
        )
    return ctx


def _exposed_headers(headers: urllib3.HTTPHeaderDict) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for name in _EXPOSED_HEADERS:
        value = headers.get(name)
        if value is not None:
            out.append((name, value[:MAX_EXPOSED_HEADER_CHARS]))
    return tuple(out)


class Urllib3PinnedTransport:
    """`egress_policy.PinnedTransport` for ONE verified destination; holds no connection between calls."""

    def __init__(
        self,
        destination: VerifiedDestination,
        ssl_context_factory: Callable[[], ssl.SSLContext],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(destination, VerifiedDestination):
            raise _fail("transport_mismatch", "a VerifiedDestination is required")
        if not callable(ssl_context_factory):
            raise _fail("transport_tls_config", "an SSL context factory is required")
        self._destination = destination
        self._factory = ssl_context_factory
        self._clock = clock

    # ---- validation -------------------------------------------------------------------------------------
    def _check_request(self, request: PinnedRequest) -> None:
        d = self._destination
        if not isinstance(request, PinnedRequest) or not isinstance(request.budget, RequestBudget):
            raise _fail("transport_mismatch", "a PinnedRequest is required")
        expected_host = d.hostname if d.port == HTTPS_DEFAULT_PORT else f"{d.hostname}:{d.port}"
        if (
            request.connect_ip not in d.addresses
            or request.port != d.port
            or request.server_hostname != d.tls_server_hostname
            or request.host_header != expected_host
            or request.method != "GET"
        ):
            raise _fail("transport_mismatch", "the request does not match the verified destination")
        try:
            ensure_relative_path(request.path_and_query)
        except EgressPolicyError:
            raise _fail("transport_mismatch", "the request path is not a plain relative path") from None

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise _fail("transport_deadline", "the total time budget is spent")
        return remaining

    # ---- execution --------------------------------------------------------------------------------------
    def execute(self, request: PinnedRequest) -> TransportResponse:
        self._check_request(request)
        budget = request.budget
        deadline = self._clock() + budget.total_timeout_s
        remaining = self._remaining(deadline)  # before connecting
        connect_t = min(budget.connect_timeout_s, remaining)
        read_t = min(budget.read_timeout_s, remaining)
        ctx = _checked_context(self._factory)
        pool = HTTPSConnectionPool(
            host=request.connect_ip,  # the validated address: urllib3 never resolves a name here
            port=request.port,
            maxsize=1,
            block=True,
            timeout=Timeout(connect=connect_t, read=read_t),
            retries=False,
            cert_reqs="CERT_REQUIRED",
            assert_hostname=request.server_hostname,
            server_hostname=request.server_hostname,  # SNI
            ssl_context=ctx,
        )
        response: urllib3.BaseHTTPResponse | None = None
        try:
            try:
                response = pool.urlopen(
                    "GET",
                    request.path_and_query,
                    headers={
                        "Host": request.host_header,
                        "Accept-Encoding": "identity",
                        "User-Agent": USER_AGENT,
                    },
                    retries=False,
                    redirect=False,
                    assert_same_host=False,  # required by IP pinning; safe only with the two lines above
                    preload_content=False,
                    decode_content=False,
                    timeout=Timeout(connect=connect_t, read=read_t),
                    pool_timeout=max(1, math.ceil(connect_t)),  # typed int; the one-use pool never contends
                )
                return self._consume(response, budget, deadline)
            except TransportError:
                raise
            except urllib3.exceptions.MaxRetryError as exc:  # not expected with retries=False; defensive
                raise self._translate(exc.reason) from None
            except Exception as exc:
                raise self._translate(exc) from None
        finally:
            if response is not None:
                response.close()
            pool.close()

    @staticmethod
    def _translate(exc: BaseException | None) -> TransportError:
        if isinstance(exc, ssl.SSLError | ssl.CertificateError | urllib3.exceptions.SSLError):
            return _fail("transport_tls", "TLS handshake or certificate verification failed")
        # NewConnectionError is a ConnectTimeoutError subclass in urllib3 2.8.0, so it must be tested first
        if isinstance(exc, urllib3.exceptions.NewConnectionError | ConnectionRefusedError):
            return _fail("transport_connect", "the connection could not be established")
        if isinstance(exc, TimeoutError | urllib3.exceptions.TimeoutError):
            return _fail("transport_timeout", "a connect, read or pool timeout elapsed")
        if isinstance(exc, urllib3.exceptions.ProtocolError | ConnectionError):
            return _fail("transport_protocol", "the connection was closed or broke the HTTP protocol")
        name = type(exc).__name__ if exc is not None else "unknown"
        return _fail("transport_error", f"transport failure ({name})")

    def _consume(
        self, response: urllib3.BaseHTTPResponse, budget: RequestBudget, deadline: float
    ) -> TransportResponse:
        status = response.status
        if not 200 <= status < 300:
            location = response.headers.get("location") if 300 <= status < 400 else None
            headers: tuple[tuple[str, str], ...] = ()
            if location is not None and len(location) <= MAX_LOCATION_CHARS:
                headers = (("location", location),)
            raise TransportStatusError(status, TransportResponse(status, headers, b""))
        encoding = response.headers.get("content-encoding")
        if encoding is not None and encoding.strip().lower() not in ("", "identity"):
            raise _fail("transport_content_encoding", "a Content-Encoding other than identity is refused")
        declared = response.headers.get("content-length")
        if declared is not None and declared.strip().isdigit() and int(declared) > budget.max_response_bytes:
            raise _fail("transport_too_large", "the declared response size exceeds the byte ceiling")
        body = bytearray()
        while True:
            self._remaining(deadline)  # before every body read
            room = budget.max_response_bytes - len(body)
            # read1(): one underlying read per call, so a slow drip cannot hide inside a blocking read()
            chunk = response.read1(amt=min(CHUNK_BYTES, room + 1), decode_content=False)
            if not chunk:
                break
            body += chunk
            if len(body) > budget.max_response_bytes:
                raise _fail("transport_too_large", "the response exceeds the byte ceiling")
        return TransportResponse(status, _exposed_headers(response.headers), bytes(body))
