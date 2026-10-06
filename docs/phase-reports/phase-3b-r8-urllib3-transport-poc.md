# Phase 3b — R8 urllib3 transport proof of concept (2026-10-06)

**Status: local proof only. Not live readiness.** Owner decision (2026-10-06): `urllib3==2.8.0` is approved **only** as the evaluated transport dependency. This is not approval of Earth Search, any host:port pair, any provider request, connector registration, or Phase 3b execution; httpx, certifi, requests, aiohttp and every other HTTP client remain excluded. The adapter is unregistered and unreachable; no request left the test process (loopback only); the fixed-query flag `APPROVED_FOR_EXECUTION` is untouched (`False`).

## 1. Shape

`geo_connectors/transport_urllib3.py` — `Urllib3PinnedTransport(destination: VerifiedDestination, ssl_context_factory, *, clock)`, implementing `egress_policy.PinnedTransport.execute(PinnedRequest) -> TransportResponse`. One transport instance serves one verified destination; each `execute` builds, uses and closes its own `HTTPSConnectionPool` (`maxsize=1`, `block=True`; no shared or global pool). The request must match the destination (address ∈ verified addresses, port, TLS name, Host header, `GET`, plain relative path) or it is refused before any socket activity (`transport_mismatch`). No URL string or caller header can enter.

| Invariant (owner list) | Where |
|---|---|
| 1 only `VerifiedDestination`/`PinnedRequest` | constructor + `_check_request`; signature test |
| 2 IP pool with `server_hostname`, `assert_hostname`, `Host` = verified hostname | pool arguments + `headers` in `execute` |
| 3 explicit verifying `SSLContext`, no bypass | `verifying_context_factory`, `_checked_context` (CERT_REQUIRED, check_hostname, TLS ≥ 1.2 or `transport_tls_config`) |
| 4 `retries=False`, `redirect=False` | pool and `urlopen`; AST test pins the literals |
| 5 identity encoding, refuse other `Content-Encoding`, `decode_content=False`, raw byte ceiling | `_consume`; tests `/gzip`, `/big`, `/stream-nolen` |
| 6 connect/read/pool timeouts + monotonic total deadline before and during reads | `Timeout(connect, read)`, `pool_timeout=connect`, `_remaining()` before the request and every body read |
| 7 no env proxies, cookies, credentials, ambient or shared state | no `PoolManager`/`ProxyManager`; fixed header set; env test |
| 8 deterministic close | `finally`: response closed, pool closed (spy tests on success and every failure path) |
| 9 reject non-2xx, no body kept, bounded metadata | `TransportStatusError` (status + bounded `Location` only); `TransportResponse` exposes `content-type`/`content-length` ≤ 256 chars |

## 2. Where urllib3's public API is relied on (all read in the installed 2.8.0 source and exercised locally)

| Boundary | API used | Basis |
|---|---|---|
| IP pinning with SNI + Host | `HTTPSConnectionPool(host=<ip>, server_hostname=…, assert_hostname=…, ssl_context=…)`, `headers={"Host": …}`, `assert_same_host=False` | documented "Custom SNI Hostname" pattern (docs/advanced-usage.rst, 2.8.0); `server_hostname`/`ssl_context` reach `HTTPSConnection` through the pool's `**conn_kw` (example-level, not a typed pool parameter) |
| Redirect/retry off | `urlopen(redirect=False, retries=False)` | `user-guide.rst`, pool source |
| Timeouts | `urllib3.Timeout(connect, read)`, `pool_timeout` | public |
| Streaming | `preload_content=False`, `HTTPResponse.read1(amt, decode_content=False)`, `.close()` | public |
| Errors | `urllib3.exceptions.{SSLError, TimeoutError, NewConnectionError, ProtocolError, MaxRetryError}` | public |

## 3. Findings that changed the design (all from the 2.8.0 source or local tests)

1. **`read(amt)` can hide a slow drip.** It blocks until `amt` bytes or EOF, so a deadline checked between calls would never fire. The adapter uses `read1()`; the `/drip` test (1 byte every 50 ms) is stopped by the 1 s deadline.
2. **`assert_hostname` makes urllib3 switch `check_hostname` off on the context and match the name itself** (`_ssl_wrap_socket_and_match_hostname`, then `_match_hostname`). Hence a fresh context per call (factory) and the hostname check is urllib3's, not the stdlib's. The wrong-certificate test proves the mismatch is refused; wildcard/IDN edge-case equivalence with the stdlib is **not** proven.
3. **`ssl.create_default_context()` reads `SSLKEYLOGFILE` and starts writing TLS secrets** (control test creates the file). The factory therefore builds `ssl.SSLContext(PROTOCOL_TLS_CLIENT)` directly.
4. **urllib3's default is `Retry(3)`**; a sensitivity control shows an endpoint that drops the connection is requested several times without `retries=False` and exactly once with it.
5. **`NewConnectionError` is a `ConnectTimeoutError` subclass** in 2.8.0; error mapping tests it first.
6. urllib3 adds a default `User-Agent: python-urllib3/2.8.0`; the adapter sends the fixed placeholder `geo-connectors-r8-poc` (the real value is an owner decision, R3). Exactly three request headers are sent: `Host`, `Accept-Encoding: identity`, `User-Agent`.

## 4. Local TLS proof (what the tests establish)

Loopback servers, a throw-away EC CA and per-name certificates generated with the `openssl` CLI at test time; names `catalog.test.example` / `other.test.example` exist only in an injected resolver; no DNS. The policy still refuses loopback, so **one autouse fixture patches `egress_policy.forbidden_reason` for 127.0.0.0/8 inside these tests only**; every other policy step is real.

Proven (`workers/connectors/tests/test_transport_urllib3_local_tls.py`, 30 tests): connection to the given IP; server-observed SNI and Host equal the logical name; certificate verified against the logical name; a certificate for another name fails (with a control that the same server succeeds under its own name); an untrusted CA fails with the system store; a second resolver answer (a second server on 127.0.0.2, same port) is never used and the resolver ran once; redirect returned not followed (one server hit, `Location` passed to `validate_redirect`, which refuses with redirects disabled); retries absent; non-2xx refused with no body exposed; `Content-Encoding: gzip` refused, `identity` accepted; byte ceiling (declared and streamed); deadline before the request, during reads (fake clock) and against a real slow drip; read timeout; refused connection; env proxies, `SSL_CERT_FILE` and `SSLKEYLOGFILE` ignored; weak contexts refused; exact pool/request arguments; pool and response closed on every path; forged requests refused before any socket event; a `sys.addaudithook` records only loopback `socket.connect` events and no resolution of the logical name from the calling thread.

Isolation (`test_transport_urllib3_isolation.py`, 9 tests + the narrowed `tests/unit/test_architecture.py` guards): only this module imports `urllib3`/`ssl`; nothing references it; importing the registry, handler and fixtures does not load `urllib3`; `live` still raises `LiveModeNotAvailable`; the dependency is exactly `urllib3==2.8.0` in `workers/connectors` only; the lock has no new transitive package and only `geo-connectors` depends on it.

## 5. System CA bundle (owner question)

The environment's system store loads (127 CA certificates here; `/etc/ssl/certs/ca-certificates.crt` exists). It is **not** sufficient for the local test server, by design: the test CA is private, so the tests pass it as an explicit `cafile`, and a negative test shows the system store rejects it. No `certifi`. Caveat observed: OpenSSL redirects the default store through `SSL_CERT_FILE` (this sandbox sets it to its proxy CA bundle), so production use should pass an explicit CA file rather than rely on the ambient store.

## 6. Dependency and licence changes

`workers/connectors/pyproject.toml`: `dependencies = ["geo-common", "urllib3==2.8.0"]`. `uv.lock`: one new package (urllib3 2.8.0, no dependencies) and the `geo-connectors` requirement. Register: one new row, `urllib3 | 2.8.0 | MIT`, in the **runtime** section. This required a generator fix: `scripts/licences.py` did not include `geo-connectors` among the runtime roots although the worker image ships it, so a connectors dependency would have been listed as "development tooling (not shipped)". Licence review `RV-0001` (package, version, scope, decision reference) is recorded in `docs/licence-acknowledgements.toml`, checked by `tests/unit/test_licences_reviews.py`; **no `[[approved]]` record and no other approval was added or changed**.

## 7. Still unproven / residual

* Real-provider behaviour (redirect/CDN hosts, rate limits, TLS chain, IPv6, HTTP/2 absence) — R1–R3 and a real transport test; nothing here touched a provider.
* A body read can block up to one read timeout, so the real total can exceed the deadline by that amount (tested bounded). **The deadline does not bound the header phase at all, see §8.**
* No proof that urllib3/OpenSSL never perform a name lookup for the numeric-IP pool beyond the audit hook (a `getaddrinfo` on the literal IP is observed; DNS packets cannot be observed here).
* ~~HTTP header-section size limits are not set by the adapter~~ — resolved in the hardening checkpoint, see §8 (what stays stack-owned is listed there).
* Equivalence of urllib3's `_match_hostname` with the stdlib for wildcard/IDN names; the `server_hostname`/`ssl_context` pool pass-through is documented by example only.
* The context factory with no `cafile` follows OpenSSL's ambient store/env.
* Remaining blockers: R1 partial, R2 unresolved, R3 unresolved, R4 owner host:port approval, R5 application + network controls, R6 start instruction, R8 not complete for live use (client not selected for any live slice; real-transport tests absent). R7 met.

## 8. Hardening checkpoint — peer address and response headers (2026-10-06; offline; loopback only)

Baseline `2e66d24`. No dependency, lock, licence-approval or fixed-query change (`APPROVED_FOR_EXECUTION` is still `False`); urllib3 is still pinned at exactly 2.8.0.

### 8.1 Peer-address assertion

* **Where.** `_PeerCheckedHTTPSConnection(HTTPSConnection).connect()` calls the parent, then `assert_peer(self.sock, selected_ip, port)`; on any failure it closes the socket and raises. It runs after TCP+TLS and **before any HTTP request is written**, so no request and no response body can exist for a wrong peer. The ClientHello (with the SNI) has already been sent to that peer; no HTTP data has.
* **Rule.** `getpeername()` must return a 2- or 4-tuple whose host is a clean IP string (no scope id) and whose port is an int, and the address must equal the **selected** `request.connect_ip` (not merely any validated address) and the port must equal the destination port. Codes: `transport_peer_unavailable` (no accessor, no socket, accessor raised), `transport_peer_malformed`, `transport_peer_mismatch`. An IPv4-mapped IPv6 form is a mismatch, never normalised into equality.
* **Supported-API assessment (recorded limitation).** urllib3 2.8.0 has **no documented accessor** for the peer address. The code relies on (a) overriding `connect()` of the public `HTTPSConnection` (`connect` is part of urllib3's `BaseHTTPConnection` protocol), (b) the pool's `ConnectionCls` attribute, assigned per pool instance, with the expected peer passed through the pool's `**conn_kw`, and (c) the `sock` attribute set by urllib3 and `http.client` — an undocumented but not underscore-private name. No `_`-prefixed urllib3 member is used. This coupling is isolated in one class and one function, verified only for 2.8.0; an upgrade must re-run the peer tests. The check fails closed if `sock` is missing.
* **What the tests prove (loopback TLS servers, real sockets).** A matching peer succeeds; the check runs on the real `SSLSocket` exactly once; the selected address (not another validated one) is what counts (a second server on 127.0.0.2, same port); a mismatching peer (other address, IPv4-mapped spelling, `::1`, wrong port) fails with the server having received **zero HTTP requests**, SNI still equal to the original hostname; the injected resolver ran exactly once; malformed and unavailable peers fail closed; the connection is closed by `connect()` itself (independent of the pool's clean-up) and the pool is closed; the audit hook saw only loopback `socket.connect` events and no resolution of the logical name.
* **Honest limit of that proof.** On loopback the kernel always reports the address that was dialled, so a *genuine* mismatch cannot be produced without privileged network setup. The mismatch and malformed paths are exercised on real TLS connections by substituting the module-level reader `_peer_address` with a faulty one; the success path uses the real reader. The mutation checks show the comparison is load-bearing.

### 8.2 Response-header policy

* **Where.** `check_response_headers(response.headers.iteritems(), limits)` is the **first** thing `_consume` does — before the status, `Location`, `Content-Encoding` or the body is looked at (tests: an over-limit response that also carries gzip or a 302 + `Location` gets the header code, and no body byte is read).
* **Limits** (`ResponseHeaderLimits`, provisional operational safeguards, not scientific thresholds): count 32, name 64 bytes, value 4096 bytes, aggregate 16384 bytes (sum of name + value + 4 per field); hard ceilings 100 / 256 / 8192 / 65536, never above what the stdlib itself accepts; invalid limits → `transport_config`.
* **Codes**, checked in this order: `transport_header_count`, `transport_header_name_size`, `transport_header_value_size`, `transport_header_malformed` (name not an RFC token, control character other than HTAB in a value, non-text or non-ISO-8859-1), `transport_header_total_size`, `transport_header_duplicate` (a repeated `Content-Length`, `Content-Encoding`, `Content-Type`, `Location` or `Transfer-Encoding`, even with identical values), `transport_header_conflict` (`Transfer-Encoding` together with `Content-Length`).
* **Tests.** Every limit accepts the exact boundary and rejects one over; each malformed/duplicate/conflict case has its own code; an ordinary STAC-like set of JSON response headers (11 fields) passes under the defaults.
* **Owned by the Python HTTP stack or urllib3 — not guaranteed by the adapter:**
  1. `http.client` reads the status line and header lines before the adapter sees anything: at most 100 fields and 65536 bytes per line (`_MAXHEADERS`, `_MAXLINE`, values read from this interpreter); beyond that it raises and the adapter reports `transport_protocol` (tested for 150 fields and a 70000-byte line). Worst-case memory held before the adapter's limits apply is therefore about 100 × 64 KiB per response.
  2. Header decoding (ISO-8859-1), continuation-line (obs-fold) handling and what the parser does with a line it cannot parse are the stdlib parser's; the adapter sees only what survives (for example `Bad(Name)` survives and is refused by the token rule). Behaviour for other unparseable lines was not characterised.
  3. urllib3 parses `Content-Length`/`Transfer-Encoding` inside `urlopen` before the adapter sees the response: differing `Content-Length` lines raise `InvalidHeader` there (reported as `transport_error`); identical repeats are accepted by urllib3 and refused later by the adapter's duplicate rule.
  4. Merged `HTTPHeaderDict` semantics: the adapter reads the raw lines through `iteritems()`.
  5. **Time spent in the header phase.** See 8.3.

### 8.3 New finding — the total deadline does not bound the header phase

Measured locally (1 s total deadline, 1 s read timeout): a server that sends one header line every 0.2 s for about 6 s, and one that sends a stream of `100 Continue` blocks for about 6 s, each kept `urlopen` busy for **6.0 s** before the deadline error fired. `http.client` resets the per-read timeout on every line and loops over `100 Continue` responses without a bound, and the adapter's deadline is only checked between its own steps. This is **not fixed** in this checkpoint (out of scope; a fix needs a watchdog or a custom response-reading path). It is recorded here and in the R8 row.

### 8.4 Local results

Tests: `test_transport_urllib3_hardening.py` (49) in addition to the 30 loopback TLS tests and 9 isolation tests; the loopback tests were repeated three times without a failure. Mutation checks (not committed): peer — no assertion, `ConnectionCls` not installed, mismatch ignored, port ignored, mapped form normalised, unavailable peer tolerated, close-on-failure removed, expected = first validated address instead of the selected one — each fails at least one test; headers — each of the seven checks removed, header check moved after the status/encoding handling, HTAB wrongly rejected — each fails at least one test. One equivalent mutant: replacing `iteritems()` by `items()` changes nothing in 2.8.0 (both iterate every raw line).

### 8.5 R8 against ADR-0014 §9 R-a…R-f — **Partial** (not Met)

| Condition | Covered offline | Not covered |
|---|---|---|
| R-a scheme/host:port/URL shape | yes (policy + tests) | — |
| R-b public addresses only | yes | metadata-name list is a short blocklist, not exhaustive |
| R-c pinning, SNI, certificate vs the original name | yes on loopback, including the peer-address assertion | a real provider's TLS chain; a genuine (kernel-level) peer mismatch |
| R-d redirects/pagination | no automatic redirects, manual ≤ 3 re-validated, downgrade refused | **pagination/asset links staying on the API base host, port and path prefix is not implemented** |
| R-e bounds | timeouts, byte ceiling, identity-only (decompression guard), no cookies/credentials, redirect and request budgets, header limits | **content-type check not implemented; page limits, JSON depth/size limits and rates are connector-level and absent; the total deadline does not cover the header phase (8.3)** |
| R-f offline tests | fake resolver and a real loopback transport; every listed attack class except as noted | pagination to another host (only the generic host allow-list applies); no fake transport |
| Client selection note (R8) | urllib3 evaluated; licence review RV-0001 | **no client is selected for any live slice; no real-provider transport test** |

Remaining blockers: R1 partial, R2 unresolved, R3 unresolved, R4 owner host:port approval, R5 application + network controls, R6 start instruction; R7 met; R8 partial as above.
