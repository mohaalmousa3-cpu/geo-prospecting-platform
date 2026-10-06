"""Offline outbound-request policy (ADR-0014 §9, R-a..R-f). PURE: no network, DNS, TLS or provider access.

Status: Phase 3b R8 *offline design and tests only*. Nothing here is wired into the registry, the handler,
the API or the worker; `CONNECTOR_MODE=live` still has no code path. No provider host or port is configured
or approved here: the allow-list is always injected by the caller (tests use invented names).

Two layers are kept apart on purpose:

* **Verified policy objects (this module).** `verify_url` / `validate_redirect` turn a string into an
  immutable `VerifiedUrl` (original hostname, explicit port, validated IPs, TLS server name) *or* raise
  `EgressPolicyError`. The resolver is an injected callable, called exactly once per verification.
* **Future transport I/O (NOT implemented).** `PinnedTransport` / `PinnedRequest` only *define* what a later
  transport must do: connect to one verified IP, send SNI and verify the certificate against the original
  hostname, never resolve a name itself, never follow a redirect. Whether a concrete client can do this is a
  property of that client and needs a real TLS integration test that this module cannot provide.

Only pure stdlib is used (`ipaddress` parsing, `re`, `math`, `dataclasses`); `socket`, `ssl`, `urllib*`,
`http*` and HTTP clients are never imported (`tests/unit/test_architecture.py` and
`workers/connectors/tests/test_egress_policy_offline.py` enforce it). URL parsing is therefore done by
hand and is deliberately stricter than RFC 3986: anything unusual is rejected, never accepted by
normalisation.

The numeric ceilings are provisional operational safeguards (plan D7 / ADR-0008 status), not scientific
thresholds.
"""

from __future__ import annotations

import ipaddress
import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from geo_connectors.errors import ConnectorError

# --- provisional hard ceilings (plan §3.3 / D7 "approved (provisional)"; JOB_TIMEOUT_SECONDS default 1800)
MAX_REQUESTS_CEILING = 50  # CONNECTOR_MAX_REQUESTS_PER_JOB
PHASE_TIMEOUT_CEILING_S = 30.0  # CONNECTOR_TIMEOUT_SECONDS (connect and read, each)
TOTAL_TIMEOUT_CEILING_S = 1800.0  # never above the job-timeout default
RESPONSE_BYTES_CEILING = 20 * 1024 * 1024  # CONNECTOR_MAX_RESPONSE_MB (20), read as MiB
MAX_REDIRECTS_CEILING = 3  # ADR-0014 R-d
MAX_URL_LENGTH = 2048
MAX_RESOLVED_ADDRESSES = 16
HTTPS_DEFAULT_PORT = 443

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class EgressPolicyError(ConnectorError):
    """A request was refused by the offline policy. `code` is stable and machine-readable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> EgressPolicyError:
    return EgressPolicyError(code, message)


# --- hostnames ------------------------------------------------------------------------------------
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
# Conservative refusals (ADR-0014 R-b "known metadata host names"); not exhaustive, and the allow-list is
# the control.
_FORBIDDEN_NAMES = frozenset({"localhost", "metadata", "instance-data"})
_FORBIDDEN_SUFFIXES = (".localhost", ".local", ".localdomain", ".internal", ".lan", ".home.arpa")


def normalise_host(raw: object) -> str:
    """Lower-case, IDNA (ASCII) form, one trailing dot removed. Rejects IP literals in any spelling and
    local names."""
    if not isinstance(raw, str) or not raw:
        raise _fail("host_malformed", "host must be a non-empty string")
    try:
        host = raw.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise _fail("host_malformed", "host is not valid IDNA") from None
    if host.endswith("."):
        host = host[:-1]
    if not host or len(host) > 253 or host.endswith("."):
        raise _fail("host_malformed", "empty or over-long host name")
    labels = host.split(".")
    if not all(_LABEL.fullmatch(label) for label in labels):
        raise _fail("host_malformed", "host labels must be [a-z0-9-] (no wildcards, no empty labels)")
    last = labels[-1]
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    # decimal (2130706433), hex (0x7f.1), octal (0177.0.0.1) and short (127.1) spellings all end in a
    # numeric label
    if is_ip or last.isdigit() or last.startswith("0x"):
        raise _fail("ip_literal_forbidden", "IP-literal hosts (any spelling) are refused")
    if host in _FORBIDDEN_NAMES or host.endswith(_FORBIDDEN_SUFFIXES):
        raise _fail("host_forbidden", "local or metadata host names are refused")
    return host


def _port(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= 65535:
        raise _fail("port_invalid", "port must be an integer in 1..65535")
    return raw


@dataclass(frozen=True)
class HostPort:
    host: str
    port: int


@dataclass(frozen=True)
class EgressAllowlist:
    """Exact `(host, port)` pairs. No wildcards, no suffix rules. An empty list denies everything."""

    entries: frozenset[HostPort]

    @classmethod
    def of(cls, pairs: Iterable[tuple[str, int]]) -> EgressAllowlist:
        return cls(frozenset(HostPort(normalise_host(h), _port(p)) for h, p in pairs))

    def hosts(self) -> frozenset[str]:
        return frozenset(e.host for e in self.entries)


# --- relative paths (never user-controlled absolute URLs) -----------------------------------------
_PATH_OK = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@/%?-]*$")


def ensure_relative_path(value: object) -> str:
    """Accept only a path-and-query that starts with a single `/`. Absolute or scheme-relative forms are
    refused."""
    if not isinstance(value, str) or not value or len(value) > MAX_URL_LENGTH:
        raise _fail("path_invalid", "path must be a non-empty string within the length limit")
    if value.startswith("//") or "://" in value or "\\" in value or "#" in value:
        raise _fail(
            "absolute_url_forbidden", "absolute, scheme-relative, backslash or fragment forms are refused"
        )
    if not _PATH_OK.fullmatch(value):
        raise _fail("path_invalid", "path contains characters outside the allowed set")
    if re.search(r"%(?![0-9A-Fa-f]{2})", value) or "%00" in value:
        raise _fail("path_invalid", "invalid percent-encoding")
    path = value.split("?", 1)[0].replace("%2e", ".").replace("%2E", ".")
    if any(seg in (".", "..") for seg in path.split("/")):
        raise _fail("path_invalid", "dot segments are refused")
    return value


# --- URL parsing (hand-written; stricter than RFC 3986) -----------------------------------------------------
@dataclass(frozen=True)
class ParsedHttpsUrl:
    host: str
    port: int
    path_and_query: str


_AUTHORITY_CHARS = re.compile(r"^[A-Za-z0-9.:-]+$")
_PORT_TEXT = re.compile(r"^[1-9][0-9]{0,4}$")


def parse_https_url(url: object) -> ParsedHttpsUrl:
    """`https` only; no user-info, fragment, IP literal or malformed authority. The port is made explicit
    (443)."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise _fail("url_malformed", "url must be a non-empty string within the length limit")
    if not url.isascii() or any(c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F for c in url) or "\\" in url:
        raise _fail("url_malformed", "non-ASCII, whitespace, control or backslash characters are refused")
    if not url[:8].lower() == "https://":
        raise _fail("scheme_not_https", "only https:// URLs are accepted")
    if "#" in url:
        raise _fail("fragment_forbidden", "URL fragments are refused")
    rest = url[8:]
    cut = min((i for i in (rest.find("/"), rest.find("?")) if i != -1), default=len(rest))
    authority, tail = rest[:cut], rest[cut:]
    if not authority:
        raise _fail("authority_malformed", "empty authority")
    if "@" in authority:
        raise _fail("userinfo_forbidden", "credentials or user-info in the URL are refused")
    if "[" in authority or "]" in authority:
        raise _fail("ip_literal_forbidden", "bracketed IPv6 literals are refused")
    if not _AUTHORITY_CHARS.fullmatch(authority) or authority.count(":") > 1:
        raise _fail("authority_malformed", "malformed authority")
    host_text, _, port_text = authority.partition(":")
    if ":" in authority:
        if not _PORT_TEXT.fullmatch(port_text) or int(port_text) > 65535:
            raise _fail("authority_malformed", "malformed or out-of-range port")
        port = int(port_text)
    else:
        port = HTTPS_DEFAULT_PORT
    host = normalise_host(host_text)
    path = ensure_relative_path(tail if tail.startswith("/") else "/" + tail if tail else "/")
    return ParsedHttpsUrl(host, port, path)


# --- address classification (R-b) -----------------------------------------------------------------
_EXTRA_DENY = tuple(
    ipaddress.ip_network(n)
    for n in (
        "100.64.0.0/10",  # CGNAT
        "169.254.0.0/16",  # link-local incl. 169.254.169.254
        "192.0.0.0/24",
        "198.18.0.0/15",
        "240.0.0.0/4",
        "fc00::/7",  # unique-local incl. fd00:ec2::254
        "fe80::/10",
        "fec0::/10",  # deprecated site-local
        "64:ff9b::/96",  # NAT64
        "64:ff9b:1::/48",
        "2002::/16",  # 6to4
        "2001::/32",  # Teredo
    )
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def forbidden_reason(addr: IPAddress) -> str | None:
    """Why this destination is refused, or None if it is a public unicast address."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return "ipv4_mapped"
    if addr.is_loopback:
        return "loopback"
    if addr.is_link_local:
        return "link_local"
    if addr.is_multicast:
        return "multicast"
    if addr.is_unspecified:
        return "unspecified"
    if addr.is_private:
        return "private"
    if addr.is_reserved:
        return "reserved"
    if any(addr.version == n.version and addr in n for n in _EXTRA_DENY):
        return "special_use"
    if not addr.is_global:
        return "not_global"
    return None


def _validate_address(text: object) -> str:
    if not isinstance(text, str) or not text or "%" in text or text != text.strip():
        raise _fail(
            "address_malformed", "resolver returned a malformed address (scope ids and spaces are refused)"
        )
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        raise _fail("address_malformed", "resolver returned a non-address value") from None
    reason = forbidden_reason(addr)
    if reason is not None:
        raise _fail(f"address_{reason}", f"resolved destination is not a public address ({reason})")
    return str(addr)  # canonical text form


Resolver = Callable[[str, int], Sequence[str]]
"""Injected name resolution. It is called ONCE per verification; this module never imports a resolver."""


# --- verified objects -----------------------------------------------------------------------------
_ISSUER = object()


@dataclass(frozen=True)
class VerifiedDestination:
    """What a future transport may connect to. Built only by `verify_url` (the token is a guard against
    accidental construction, not a security boundary)."""

    hostname: str  # original (normalised) host name, kept for TLS and the Host header
    port: int  # explicit
    addresses: tuple[str, ...]  # every address the single resolution returned; all validated public
    tls_server_hostname: str  # SNI and certificate-verification name: always `hostname`, never an address
    _issuer: object = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer is not _ISSUER:
            raise TypeError("VerifiedDestination can only be produced by verify_url()")


@dataclass(frozen=True)
class VerifiedUrl:
    destination: VerifiedDestination
    path_and_query: str


def verify_url(url: object, allowlist: EgressAllowlist, resolver: Resolver) -> VerifiedUrl:
    """Parse, check the exact allow-list, resolve exactly once, validate every answer. Pure apart from
    `resolver`."""
    parsed = parse_https_url(url)
    pair = HostPort(parsed.host, parsed.port)
    if pair not in allowlist.entries:
        code = "port_not_allowed" if parsed.host in allowlist.hosts() else "host_not_allowed"
        raise _fail(code, "destination is not in the explicit (host, port) allow-list")
    try:
        answers = resolver(parsed.host, parsed.port)  # the ONLY resolution for this request
    except Exception as exc:  # the injected resolver may raise anything; report without its message
        raise _fail("resolution_failed", f"name resolution failed ({type(exc).__name__})") from None
    if not isinstance(answers, list | tuple) or not 1 <= len(answers) <= MAX_RESOLVED_ADDRESSES:
        raise _fail("resolution_invalid", "resolver must return 1..16 addresses as a list or tuple")
    addresses = tuple(dict.fromkeys(_validate_address(a) for a in answers))  # one bad answer rejects all
    dest = VerifiedDestination(parsed.host, parsed.port, addresses, parsed.host, _ISSUER)
    return VerifiedUrl(dest, parsed.path_and_query)


# --- budgets (pure values) ------------------------------------------------------------------------
def _bounded_int(name: str, v: object, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise _fail("budget_invalid", f"{name} must be an integer in {lo}..{hi}")
    return v


def _bounded_seconds(name: str, v: object, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v) or not 0 < v <= hi:
        raise _fail("budget_invalid", f"{name} must be a finite number in (0, {hi}]")
    return float(v)


@dataclass(frozen=True)
class RequestBudget:
    """Explicit per-job bounds. Every field is required except `max_redirects`, which defaults to 0
    (disabled)."""

    max_requests: int
    connect_timeout_s: float
    read_timeout_s: float
    total_timeout_s: float
    max_response_bytes: int
    max_redirects: int = 0

    def __post_init__(self) -> None:
        _bounded_int("max_requests", self.max_requests, 1, MAX_REQUESTS_CEILING)
        c = _bounded_seconds("connect_timeout_s", self.connect_timeout_s, PHASE_TIMEOUT_CEILING_S)
        r = _bounded_seconds("read_timeout_s", self.read_timeout_s, PHASE_TIMEOUT_CEILING_S)
        t = _bounded_seconds("total_timeout_s", self.total_timeout_s, TOTAL_TIMEOUT_CEILING_S)
        if t < max(c, r):
            raise _fail("budget_invalid", "total_timeout_s must not be below the connect or read timeout")
        _bounded_int("max_response_bytes", self.max_response_bytes, 1, RESPONSE_BYTES_CEILING)
        _bounded_int("max_redirects", self.max_redirects, 0, MAX_REDIRECTS_CEILING)


def require_request_allowed(budget: RequestBudget, requests_made: int) -> None:
    _bounded_int("requests_made", requests_made, 0, 10**9)
    if requests_made >= budget.max_requests:
        raise _fail("request_budget_exhausted", "the per-job request budget is spent")


def require_response_size(budget: RequestBudget, size: int) -> None:
    _bounded_int("size", size, 0, 10**12)
    if size > budget.max_response_bytes:
        raise _fail("response_too_large", "response exceeds the byte ceiling")


# --- redirects: never followed here; a candidate redirect is a brand-new, fully validated URL -----
@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes = b""


def redirect_location(response: TransportResponse) -> str | None:
    """The `Location` of a redirect response, or None. Does not follow, resolve or validate anything."""
    if response.status not in _REDIRECT_STATUSES:
        return None
    values = [v for k, v in response.headers if k.lower() == "location"]
    if len(values) != 1:
        raise _fail("redirect_invalid", "a redirect needs exactly one Location header")
    return values[0]


def validate_redirect(
    location: object,
    *,
    allowlist: EgressAllowlist,
    resolver: Resolver,
    budget: RequestBudget,
    redirects_followed: int,
) -> VerifiedUrl:
    """Future entry point for a manual redirect hop. Disabled unless `budget.max_redirects > 0`.

    The new URL gets the complete treatment of `verify_url` (https, exact allow-list, a fresh single
    resolution,
    address validation). Relative `Location` values and downgrades are refused. Nothing is requested here."""
    if budget.max_redirects == 0:
        raise _fail("redirects_disabled", "redirects are disabled by default; this budget does not allow any")
    _bounded_int("redirects_followed", redirects_followed, 0, 10**6)
    if redirects_followed >= budget.max_redirects:
        raise _fail("too_many_redirects", "redirect budget exhausted")
    if not isinstance(location, str) or "://" not in location:
        raise _fail("redirect_not_absolute", "a redirect target must be a complete absolute https URL")
    return verify_url(location, allowlist, resolver)


# --- future transport contract (DEFINITION ONLY; no implementation exists in this repository) ---------------
@dataclass(frozen=True)
class PinnedRequest:
    """Everything a future transport needs, and nothing it may decide for itself."""

    connect_ip: str  # the ONLY address to connect to (one of the verified addresses)
    port: int
    server_hostname: str  # SNI and certificate hostname verification: the original name, never `connect_ip`
    host_header: str
    method: str  # "GET" only
    path_and_query: str
    budget: RequestBudget
    # There is deliberately no `follow_redirects` field: redirects are never followed by a transport.


def plan_pinned_request(target: VerifiedUrl, budget: RequestBudget, *, requests_made: int) -> PinnedRequest:
    """Pure: pick the verified address and bind the request to it. Raises when the request budget is spent."""
    require_request_allowed(budget, requests_made)
    d = target.destination
    host_header = d.hostname if d.port == HTTPS_DEFAULT_PORT else f"{d.hostname}:{d.port}"
    return PinnedRequest(
        d.addresses[0], d.port, d.tls_server_hostname, host_header, "GET", target.path_and_query, budget
    )


class PinnedTransport(Protocol):
    """Contract for a FUTURE transport (not implemented; selecting one is a separate, owner-approved
    step, R8).

    An implementation MUST: open the connection to `request.connect_ip:request.port` only; never resolve
    a name;
    send `request.server_hostname` as SNI and verify the server certificate against that name (not the IP);
    refuse plain HTTP; return 3xx responses to the caller without following them; send no cookies,
    credentials or
    caller-supplied headers; enforce `budget` (connect/read/total timeouts, byte ceiling while streaming) and
    ignore environment proxy settings. Whether a given library can satisfy this is NOT proven by this
    repository.
    """

    def execute(self, request: PinnedRequest) -> TransportResponse: ...
