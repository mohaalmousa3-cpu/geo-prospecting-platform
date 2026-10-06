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
* A body read can block up to one read timeout, so the real total can exceed the deadline by that amount (tested bounded).
* No proof that urllib3/OpenSSL never perform a name lookup for the numeric-IP pool beyond the audit hook (a `getaddrinfo` on the literal IP is observed; DNS packets cannot be observed here).
* HTTP header-section size limits are not set by the adapter (`http.client` defaults).
* Equivalence of urllib3's `_match_hostname` with the stdlib for wildcard/IDN names; the `server_hostname`/`ssl_context` pool pass-through is documented by example only.
* The context factory with no `cafile` follows OpenSSL's ambient store/env.
* Remaining blockers: R1 partial, R2 unresolved, R3 unresolved, R4 owner host:port approval, R5 application + network controls, R6 start instruction, R8 not complete for live use (client not selected for any live slice; real-transport tests absent). R7 met.
