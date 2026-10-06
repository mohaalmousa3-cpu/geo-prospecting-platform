# Phase 3b — R8 offline HTTP-security design note (2026-10-06)

**Status: offline design and tests only. Not live readiness.** No provider host or port is approved; no HTTP client is selected or installed (`urllib3` is only the owner's preferred *candidate for evaluation*); nothing is wired into the registry, handler, API or worker; `CONNECTOR_MODE=live` still returns 501 / fails with "not available". Candidate (not approved) scope per the owner: Earth Search v1, collection `sentinel-2-l2a`. Binding decisions: ADR-0014 §9, ADR-0008, ADR-0011.

## 1. Verified policy objects vs future transport I/O

| Layer | Exists now | What it does |
|---|---|---|
| **Policy (pure)** `geo_connectors/egress_policy.py` | yes | URL → `VerifiedUrl` (immutable: original hostname, explicit port, validated IPs, TLS server name) or `EgressPolicyError` with a stable `code`. The resolver is an **injected callable**, called **exactly once** per verification. Budgets are frozen values. |
| **Fixed queries (pure)** `geo_connectors/fixed_query.py` | yes | Two named *candidate* verification queries (`collection_metadata`, `search_probe`), accepted only by name; **not authorised to execute** (`APPROVED_FOR_EXECUTION = False`). No host, AOI, project, header, cookie, credential, user bbox/datetime or endpoint path can be expressed. |
| **Transport (network I/O)** | **no** | `PinnedTransport` (a `Protocol`) and `PinnedRequest` only *define* the contract: connect to one verified IP, SNI and certificate verification against the original hostname, never resolve, never follow redirects. No implementation, no client, no socket. |

Only pure stdlib is imported (`ipaddress` parsing, `re`, `math`, `dataclasses`). URL parsing is hand-written and stricter than RFC 3986, because `urllib` is deliberately off-limits to this package. `ipaddress` does not touch the network.

## 2. ADR-0014 R-a … R-f → code and tests

Tests: `workers/connectors/tests/test_egress_policy.py` (150), `test_fixed_query.py` (51), `test_egress_policy_offline.py` (7); all offline, fake resolvers only, invented host `catalog.example`.

| Invariant | Code (`egress_policy.py` unless noted) | Tests (name prefixes) | Gaps (explicit) |
|---|---|---|---|
| **R-a** https only; exact `(host, port)` pairs; no wildcards; lower-case/IDNA/trailing-dot; no user-info, IP literals, other ports; no user URL parts | `parse_https_url`, `normalise_host`, `EgressAllowlist.of`, `verify_url`, `ensure_relative_path`; `fixed_query.from_mapping` | `test_accepts_https…`, `test_host_is_normalised…`, `test_malformed_or_forbidden_urls…` (credentials, fragments, malformed authority, decimal/hex/octal/short IP spellings, bracketed IPv6, `localhost`, `*.example`, backslash), `test_only_the_exact_host_port_pair…`, `test_empty_allowlist…`, `test_idna_…`, `test_user_supplied_absolute_or_traversal_paths…` | The metadata-name list is a short conservative blocklist (`_FORBIDDEN_NAMES/_SUFFIXES`), not exhaustive: the allow-list is the control. |
| **R-b** every resolved address public; mapped forms refused | `forbidden_reason`, `_validate_address` (loopback, link-local incl. `169.254.169.254`, multicast, unspecified, private, reserved, CGNAT, unique-local incl. `fd00:ec2::254`, site-local, NAT64, 6to4, Teredo, any IPv4-mapped; scope ids and non-canonical spellings refused; one bad answer rejects the whole answer set) | `test_every_forbidden_address_class_is_rejected` (IPv4 and IPv6 tables), `test_ipv4_mapped_forms…`, `test_resolver_values_that_are_not_clean_addresses…`, `test_one_bad_answer…`, `test_resolver_failures_and_wrong_shapes…` | Classification relies on the stdlib `ipaddress` tables plus the explicit extra list; it varies slightly across Python patch versions (hence the explicit list). |
| **R-c** address pinning + TLS name | `VerifiedDestination` (hostname, port, addresses, `tls_server_hostname`; unforgeable-by-accident token), `plan_pinned_request`, `PinnedRequest`, `PinnedTransport` | `test_dns_rebinding_is_defeated…` (safe first answer, forbidden second; one resolver call), `test_each_verification_resolves_once…`, `test_verified_destination_keeps_the_hostname_as_tls_name…`, `test_verified_objects_are_immutable…`, `test_pinned_request_plan_binds_ip_sni_and_host_header…` | **Not provable here:** that a real client actually connects to `connect_ip`, sends SNI, verifies the certificate against the name, and never resolves again (see §3). |
| **R-d** no automatic redirects; manual ≤ 3, each fully re-validated; `https→http` refused; pagination/asset links untrusted | `RequestBudget.max_redirects` (default 0), `redirect_location` (reads only), `validate_redirect` (relative targets refused; full `verify_url` with a fresh single resolution; nothing is fetched) | `test_redirects_are_disabled_by_default…`, `test_redirect_location_only_reads…`, `test_a_candidate_redirect_gets_full_independent_validation…`, `test_bad_redirect_targets…` (downgrade, relative, other host, other port, metadata address, user-info), `test_redirect_to_an_allowed_name_that_resolves_to_a_forbidden_address…`, `test_redirect_count_is_bounded` | **Pagination path-prefix check (same host, port *and* API path prefix) is not implemented**: `verify_url` checks host and port only. Pagination links are untrusted but their policy needs the future connector's API base and is deferred. |
| **R-e** bounds | `RequestBudget` (requests ≤ 50, connect/read ≤ 30 s, total ≤ 1800 s, response ≤ 20 MiB, redirects ≤ 3; explicit, immutable, bool/NaN/inf/zero/negative refused), `require_request_allowed`, `require_response_size`, `plan_pinned_request` | `test_budgets_reject_zero_negative_and_out_of_range_values` (28 cases), `test_budget_boundaries…`, `test_budget_checks_are_pure`, `test_plan_refuses_when_the_request_budget_is_spent` | Content-type check, decompression guard, JSON depth/size, page limit, retries/back-off, per-minute rate and "no cookies / no credentials" are **transport- or connector-level** and are only stated in the `PinnedTransport` contract. Ceilings are the provisional plan-D7 values (not scientific thresholds); `disabled`/`fixture` no-socket evidence is the Phase 3a test. |
| **R-f** offline fake resolver/transport tests | the fake resolver is a test double; **no fake transport exists** | spellings, `localhost`, user-info trick, wrong port, downgrade, redirect to metadata / non-permitted host, DNS rebinding: as above; oversized response: `require_response_size` (size check only) | "Pagination to another host" is covered only by the generic host allow-list (different host refused); same-host different-path is the deferred item above. A fake *transport* is deferred with the client choice. |
| Module is offline and unwired | — | `test_egress_policy_offline.py`: AST scan (imports ⊆ pure stdlib; none of socket/ssl/urllib/http/httpx/requests/urllib3/aiohttp/asyncio/subprocess/importlib/os…; no `open/eval/exec/__import__`, no network calls), "not referenced by any other source file", registry still `LiveModeNotAvailable`, and a subprocess audit-hook run of the whole policy (no `socket.*`/`ssl.*`/`urllib.*` events, no network module loaded) | An audit hook proves absence for the exercised paths; the static scan covers the rest. This is a test control, not an egress firewall. |

Mutation check (local, not committed): removing the single-resolution rule, the port comparison, the user-info refusal, the https check, the redirect-disabled gate, the IPv4-mapped rule, or pointing the TLS name at the IP each makes at least one test fail.

## 3. What cannot be proven without a real transport / TLS integration test

1. The connection really goes to the pinned `connect_ip` (no second DNS lookup inside the library, no happy-eyeballs fallback to another address, no keep-alive reuse to a different peer).
2. SNI is sent and the certificate is verified against the **hostname**, not the IP; CA-bundle source and TLS minimum version.
3. Environment/system proxy settings are ignored (behind a proxy the "resolved address" is the proxy's).
4. The client returns 3xx instead of following it, sends no cookies/credentials/extra headers, and refuses plain HTTP.
5. Streaming byte ceiling, decompression guard, content-type check, and connect/read/**total** timeouts behave as the budget states (libraries differ on what "read timeout" and "total" mean).
6. Behaviour with real provider responses: redirect/CDN/pagination hosts (R1), rate limiting (R3).
7. That any concrete library satisfies the contract at all: ADR-0014 §9 calls this a requirement to validate, not an established capability.

## 4. Remaining blockers (R1–R8)

| Item | State after this checkpoint |
|---|---|
| R1 hosts/ports from official docs | **Partially Met** (base URL and candidate `earth-search.aws.element84.com:443` known; redirects, CDN, pagination host, asset hosts unresolved; several official domains were blocked from the research sandbox) |
| R2 terms, licences, attribution | **Unresolved** |
| R3 limits, costs | **Unresolved** (no published rate limits) |
| R4 host/port approval or owner-run check | **Pending owner** |
| R5 application + network controls for the approved hosts | **Pending** (this module is only a part of the application controls; no network control exists) |
| R6 explicit start instruction | **Not given** |
| R7 F-1 closed | **Met** (2026-10-06) |
| R8 client selection note, offline tests R-a–R-f, licence review (ADR §10) | **Partial**: offline policy tests exist; **no client selected**, no licence review recorded, no transport-level tests |

This note does not approve live networking, a provider, hosts, ports, a client, a dependency, or Phase 3b implementation.
