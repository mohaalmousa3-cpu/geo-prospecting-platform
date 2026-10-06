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

Peer address (hardening checkpoint): after the connection is established (TCP and TLS) and BEFORE any HTTP
request is written, the connection's actual peer address (`getpeername()`) must equal the selected, validated
pinned IP and port exactly; unavailable, malformed or different values fail closed. urllib3 2.8.0 has no
documented accessor for this: the check overrides `connect()` of the public `HTTPSConnection` (a member of
urllib3's connection protocol) and reads the `sock` attribute set by urllib3 and `http.client` (not an
underscore-private name, but not in the documented protocol either). The pool's `ConnectionCls` attribute is
set per pool instance. This coupling is isolated in `_PeerCheckedHTTPSConnection` / `_peer_address`, is
verified only for the pinned 2.8.0, and any urllib3 upgrade needs the peer tests re-run. The ClientHello (with
the SNI) has already been sent when the check runs; no HTTP data has.

Response headers: explicit limits (`ResponseHeaderLimits`: count, name length, value length, aggregate bytes)
and RFC token / control-character / duplicate-sensitive-field checks run on the raw header lines FIRST, before
the status, `Content-Encoding`, `Location` or the body are looked at. What stays owned by the Python HTTP
stack and cannot be guaranteed by this adapter is listed in the design note (stdlib line and field-count caps,
obs-fold and charset handling, `Content-Length`/`Transfer-Encoding` parsing inside urllib3 before the adapter
sees the response, and the time spent in the header phase).

Known limit: a body read can block for at most the read timeout, so the real total can exceed the deadline
by up to one read timeout. Not proven here: behaviour against a real provider, real DNS, proxies in the
network path.
"""

from __future__ import annotations

import ipaddress
import math
import re
import ssl
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import urllib3.exceptions
from urllib3 import HTTPSConnectionPool, Timeout
from urllib3.connection import HTTPSConnection

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


# ---- response-header policy -------------------------------------------------------------------------
# Provisional operational safeguards (like the ADR-0008 limits), not scientific thresholds. Sized for ordinary
# JSON API responses (a STAC-like response carries roughly 8-20 header fields); the ceilings never exceed what
# the Python HTTP stack itself accepts (100 fields, 65536 bytes per line).
HEADER_COUNT_CEILING = 100
HEADER_NAME_CEILING = 256
HEADER_VALUE_CEILING = 8192
HEADER_TOTAL_CEILING = 65536
_HEADER_FRAMING_BYTES = 4  # ": " and CRLF, counted per field in the aggregate
_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")  # HTAB is the only control character allowed in a value
_DUPLICATE_SENSITIVE = frozenset(
    {"content-length", "content-encoding", "content-type", "location", "transfer-encoding"}
)


@dataclass(frozen=True)
class ResponseHeaderLimits:
    """Bounds on the response header section, checked on the raw (unmerged) header lines."""

    max_count: int = 32
    max_name_bytes: int = 64
    max_value_bytes: int = 4096
    max_total_bytes: int = 16384  # sum over fields of len(name) + len(value) + 4

    def __post_init__(self) -> None:
        for name, value, ceiling in (
            ("max_count", self.max_count, HEADER_COUNT_CEILING),
            ("max_name_bytes", self.max_name_bytes, HEADER_NAME_CEILING),
            ("max_value_bytes", self.max_value_bytes, HEADER_VALUE_CEILING),
            ("max_total_bytes", self.max_total_bytes, HEADER_TOTAL_CEILING),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
                raise _fail("transport_config", f"{name} must be an integer in 1..{ceiling}")


DEFAULT_HEADER_LIMITS = ResponseHeaderLimits()


def check_response_headers(fields: Iterable[tuple[str, str]], limits: ResponseHeaderLimits) -> None:
    """Refuse an over-limit, malformed or duplicate-sensitive header section. `fields` must be the raw lines
    (duplicates kept). Order of checks, each with its own stable code: count, name length, value length,
    malformed name/value, aggregate size, duplicate-sensitive repeats, Transfer-Encoding plus Content-Length.
    """
    items = list(fields)
    if len(items) > limits.max_count:
        raise _fail("transport_header_count", "too many response header fields")
    total = 0
    seen: dict[str, int] = {}
    for name, value in items:
        if not isinstance(name, str) or not isinstance(value, str):
            raise _fail("transport_header_malformed", "a header name or value is not text")
        try:
            name_bytes, value_bytes = len(name.encode("latin-1")), len(value.encode("latin-1"))
        except UnicodeEncodeError:
            raise _fail(
                "transport_header_malformed", "a header contains a character outside ISO-8859-1"
            ) from None
        if name_bytes > limits.max_name_bytes:
            raise _fail("transport_header_name_size", "a response header name is too long")
        if value_bytes > limits.max_value_bytes:
            raise _fail("transport_header_value_size", "a response header value is too long")
        if not _TOKEN.fullmatch(name) or _CONTROL.search(value):
            raise _fail("transport_header_malformed", "a response header name or value is malformed")
        total += name_bytes + value_bytes + _HEADER_FRAMING_BYTES
        key = name.lower()
        seen[key] = seen.get(key, 0) + 1
    if total > limits.max_total_bytes:
        raise _fail("transport_header_total_size", "the response header section is too large")
    if any(n > 1 and k in _DUPLICATE_SENSITIVE for k, n in seen.items()):
        raise _fail("transport_header_duplicate", "a field that must not repeat appears more than once")
    if "transfer-encoding" in seen and "content-length" in seen:
        raise _fail("transport_header_conflict", "Transfer-Encoding and Content-Length are both present")


# ---- peer-address assertion -------------------------------------------------------------------------
def _peer_address(sock: object) -> object:
    """The one place the connection's peer is read (module-level so tests can substitute a faulty reader)."""
    getter = getattr(sock, "getpeername", None)
    if not callable(getter):
        raise AttributeError("no peer address accessor")
    return getter()


def assert_peer(sock: object, expected_ip: str, expected_port: int) -> None:
    """Fail closed unless the connected peer is exactly `expected_ip:expected_port` (strict: IPv4-mapped IPv6
    form, a scope id or any other spelling is a mismatch or malformed, never normalised into equality)."""
    try:
        raw = _peer_address(sock)
    except Exception:
        raise _fail("transport_peer_unavailable", "the connection's peer address is not available") from None
    if not isinstance(raw, tuple) or len(raw) not in (2, 4):
        raise _fail("transport_peer_malformed", "the peer address has an unexpected shape")
    host, port = raw[0], raw[1]
    if not isinstance(host, str) or "%" in host or isinstance(port, bool) or not isinstance(port, int):
        raise _fail("transport_peer_malformed", "the peer address is malformed")
    try:
        actual = ipaddress.ip_address(host)
    except ValueError:
        raise _fail("transport_peer_malformed", "the peer address is not an IP address") from None
    if actual != ipaddress.ip_address(expected_ip) or port != expected_port:
        raise _fail("transport_peer_mismatch", "the connected peer is not the pinned, validated address")


class _PeerCheckedHTTPSConnection(HTTPSConnection):
    """`HTTPSConnection` whose `connect()` asserts the peer before any request can be written."""

    def __init__(
        self, *args: object, expected_peer_ip: str, expected_peer_port: int, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._expected_peer_ip = expected_peer_ip
        self._expected_peer_port = expected_peer_port

    def connect(self) -> None:
        super().connect()
        try:
            assert_peer(self.sock, self._expected_peer_ip, self._expected_peer_port)
        except BaseException:
            self.close()  # never leave a connection to an unverified peer open
            raise


class Urllib3PinnedTransport:
    """`egress_policy.PinnedTransport` for ONE verified destination; holds no connection between calls."""

    def __init__(
        self,
        destination: VerifiedDestination,
        ssl_context_factory: Callable[[], ssl.SSLContext],
        *,
        clock: Callable[[], float] = time.monotonic,
        header_limits: ResponseHeaderLimits | None = None,
    ) -> None:
        if header_limits is not None and not isinstance(header_limits, ResponseHeaderLimits):
            raise _fail("transport_config", "header_limits must be a ResponseHeaderLimits")
        if not isinstance(destination, VerifiedDestination):
            raise _fail("transport_mismatch", "a VerifiedDestination is required")
        if not callable(ssl_context_factory):
            raise _fail("transport_tls_config", "an SSL context factory is required")
        self._destination = destination
        self._factory = ssl_context_factory
        self._clock = clock
        self._limits = header_limits or DEFAULT_HEADER_LIMITS

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
            expected_peer_ip=request.connect_ip,  # reaches _PeerCheckedHTTPSConnection via the pool's conn_kw
            expected_peer_port=request.port,
        )
        pool.ConnectionCls = _PeerCheckedHTTPSConnection
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
        # every raw header line, duplicates kept (`iteritems()` is the documented way; `items()` is a set
        # subclass that iterates identically in 2.8.0); checked before anything in the response is used
        check_response_headers(response.headers.iteritems(), self._limits)
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
