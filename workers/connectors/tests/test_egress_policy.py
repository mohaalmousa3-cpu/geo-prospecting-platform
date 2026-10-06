"""Offline tests of the egress policy (ADR-0014 R-a..R-f). Every resolver and transport here is an injected fake;
host names are invented (`catalog.example`) and no provider host is configured anywhere."""

from __future__ import annotations

import dataclasses
import ipaddress

import pytest

from geo_connectors.egress_policy import (
    EgressAllowlist,
    EgressPolicyError,
    RequestBudget,
    TransportResponse,
    VerifiedDestination,
    VerifiedUrl,
    ensure_relative_path,
    forbidden_reason,
    normalise_host,
    plan_pinned_request,
    redirect_location,
    require_request_allowed,
    require_response_size,
    validate_redirect,
    verify_url,
)

HOST = "catalog.example"
PUBLIC4 = "8.8.8.8"
PUBLIC6 = "2606:4700:4700::1111"
ALLOW = EgressAllowlist.of([(HOST, 443)])


class FakeResolver:
    """Returns a scripted answer per call and records every call: a second call would reveal a re-resolution."""

    def __init__(self, *answers: list[str] | Exception) -> None:
        self.answers = list(answers) or [[PUBLIC4]]
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append((host, port))
        a = self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]
        if isinstance(a, Exception):
            raise a
        return a


def budget(**kw: object) -> RequestBudget:
    base: dict[str, object] = {
        "max_requests": 5,
        "connect_timeout_s": 5,
        "read_timeout_s": 10,
        "total_timeout_s": 30,
        "max_response_bytes": 1024,
    }
    base.update(kw)
    return RequestBudget(**base)  # type: ignore[arg-type]


def code_of(fn: object, *a: object, **kw: object) -> str:
    with pytest.raises(EgressPolicyError) as e:
        fn(*a, **kw)  # type: ignore[operator]
    return e.value.code


# ---- R-a: scheme, host:port, URL shape ---------------------------------------------------------------------
def test_accepts_https_with_exact_host_and_default_port_made_explicit() -> None:
    r = FakeResolver()
    v = verify_url(f"https://{HOST}/v1/collections/x?limit=1", ALLOW, r)
    assert (v.destination.hostname, v.destination.port) == (HOST, 443)
    assert v.path_and_query == "/v1/collections/x?limit=1"


def test_host_is_normalised_before_the_allowlist_comparison() -> None:
    for url in (f"https://{HOST.upper()}/", f"HTTPS://{HOST}./", f"https://{HOST}:443/"):
        assert verify_url(url, ALLOW, FakeResolver()).destination.hostname == HOST


@pytest.mark.parametrize(
    ("url", "code"),
    [
        (f"http://{HOST}/", "scheme_not_https"),
        (f"ftp://{HOST}/", "scheme_not_https"),
        (f"//{HOST}/", "scheme_not_https"),
        (f"https:/{HOST}/", "scheme_not_https"),
        (f"{HOST}/", "scheme_not_https"),
        (f"https://user@{HOST}/", "userinfo_forbidden"),
        (f"https://user:pw@{HOST}/", "userinfo_forbidden"),
        (f"https://{HOST}@evil.example/", "userinfo_forbidden"),
        (f"https://evil.example@{HOST}/", "userinfo_forbidden"),
        (f"https://{HOST}/#frag", "fragment_forbidden"),
        (f"https://{HOST}/p#frag", "fragment_forbidden"),
        (f"https://{HOST}:/", "authority_malformed"),
        (f"https://{HOST}:abc/", "authority_malformed"),
        (f"https://{HOST}:443:443/", "authority_malformed"),
        (f"https://{HOST}:0443/", "authority_malformed"),
        (f"https://{HOST}:65536/", "authority_malformed"),
        (f"https://{HOST}:-1/", "authority_malformed"),
        ("https:///path", "authority_malformed"),
        (f"https://{HOST}\\@evil.example/", "url_malformed"),
        (f"https://{HOST}/a b", "url_malformed"),
        (f"https://{HOST}/\n", "url_malformed"),
        ("https://caf\u00e9.example/", "url_malformed"),
        ("https://[::1]/", "ip_literal_forbidden"),
        ("https://[2606:4700:4700::1111]:443/", "ip_literal_forbidden"),
        ("https://8.8.8.8/", "ip_literal_forbidden"),
        ("https://8.8.8.8:443/", "ip_literal_forbidden"),
        ("https://2130706433/", "ip_literal_forbidden"),  # decimal 127.0.0.1
        ("https://0x7f000001/", "ip_literal_forbidden"),  # hex
        ("https://0x7f.0.0.1/", "ip_literal_forbidden"),
        ("https://0177.0.0.1/", "ip_literal_forbidden"),  # octal
        ("https://127.1/", "ip_literal_forbidden"),  # short form
        ("https://localhost/", "host_forbidden"),
        ("https://a.localhost/", "host_forbidden"),
        ("https://metadata.google.internal/", "host_forbidden"),
        ("https://*.example/", "authority_malformed"),
        ("https://a..example/", "host_malformed"),
        (f"https://{HOST}../", "host_malformed"),
    ],
)
def test_malformed_or_forbidden_urls_are_refused_before_any_resolution(url: str, code: str) -> None:
    r = FakeResolver()
    assert code_of(verify_url, url, ALLOW, r) == code
    assert r.calls == []  # nothing was resolved for a refused URL


@pytest.mark.parametrize(
    "bad", [None, 5, b"https://catalog.example/", "", "h" * 3000, ["https://catalog.example/"]]
)
def test_non_string_or_oversized_urls_are_refused(bad: object) -> None:
    assert code_of(verify_url, bad, ALLOW, FakeResolver()) == "url_malformed"


def test_only_the_exact_host_port_pair_is_allowed() -> None:
    r = FakeResolver()
    assert code_of(verify_url, "https://other.example/", ALLOW, r) == "host_not_allowed"
    assert (
        code_of(verify_url, f"https://sub.{HOST}/", ALLOW, r) == "host_not_allowed"
    )  # no suffix/wildcard rule
    assert code_of(verify_url, f"https://{HOST}.evil.example/", ALLOW, r) == "host_not_allowed"
    assert (
        code_of(verify_url, f"https://{HOST}:8443/", ALLOW, r) == "port_not_allowed"
    )  # non-default, not approved
    assert code_of(verify_url, f"https://{HOST}:444/", ALLOW, r) == "port_not_allowed"
    assert r.calls == []
    # an approved non-default pair is accepted only as that exact pair
    allow = EgressAllowlist.of([(HOST, 8443)])
    assert verify_url(f"https://{HOST}:8443/x", allow, FakeResolver()).destination.port == 8443
    assert code_of(verify_url, f"https://{HOST}/x", allow, r) == "port_not_allowed"


def test_empty_allowlist_denies_everything_and_allowlist_rejects_unsafe_entries() -> None:
    assert (
        code_of(verify_url, f"https://{HOST}/", EgressAllowlist.of([]), FakeResolver()) == "host_not_allowed"
    )
    for host, port, code in [
        ("*.example", 443, "host_malformed"),
        ("8.8.8.8", 443, "ip_literal_forbidden"),
        ("localhost", 443, "host_forbidden"),
        (HOST, 0, "port_invalid"),
        (HOST, 70000, "port_invalid"),
        (HOST, True, "port_invalid"),
    ]:
        assert code_of(EgressAllowlist.of, [(host, port)]) == code, (host, port)


def test_allowlist_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ALLOW.entries = frozenset()  # type: ignore[misc]
    assert isinstance(ALLOW.entries, frozenset)


def test_idna_and_trailing_dot_normalisation() -> None:
    assert normalise_host("Catalog.Example.") == HOST
    assert normalise_host("xn--bcher-kva.example") == "xn--bcher-kva.example"
    assert normalise_host("b\u00fccher.example") == "xn--bcher-kva.example"


# ---- user-controlled absolute URLs --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example/x",
        "//evil.example/x",
        "/\\evil.example",
        "http://x/",
        "/x://y",
        "x",
        "",
        "/a#b",
        "/../x",
        "/a/%2e%2e/b",
    ],
)
def test_user_supplied_absolute_or_traversal_paths_are_refused(value: str) -> None:
    with pytest.raises(EgressPolicyError):
        ensure_relative_path(value)


def test_relative_path_accepts_a_plain_path_and_query() -> None:
    assert ensure_relative_path("/v1/search?limit=1&bbox=0,0,1,1") == "/v1/search?limit=1&bbox=0,0,1,1"


# ---- R-b: forbidden destinations (IPv4 and IPv6) -------------------------------------------------------------
FORBIDDEN_V4 = {
    "127.0.0.1": "loopback",
    "127.255.255.254": "loopback",
    "10.0.0.1": "private",
    "172.16.0.1": "private",
    "192.168.1.1": "private",
    "169.254.169.254": "link_local",
    "100.64.0.1": "special_use",  # CGNAT
    "0.0.0.0": "unspecified",
    "224.0.0.1": "multicast",
    "255.255.255.255": "reserved",
    "240.0.0.1": "reserved",
    "192.0.2.1": "private",  # documentation range (stdlib classes it private); refused either way
    "198.18.0.1": "private",
}
FORBIDDEN_V6 = {
    "::1": "loopback",
    "::": "unspecified",
    "fe80::1": "link_local",
    "fc00::1": "private",
    "fd00:ec2::254": "private",  # EC2 IPv6 metadata address
    "ff02::1": "multicast",
    "::ffff:127.0.0.1": "ipv4_mapped",
    "::ffff:8.8.8.8": "ipv4_mapped",  # even a public mapped address is refused (ADR R-b)
    "64:ff9b::808:808": "special_use",
    "2002:7f00:1::": "private",
    "2001:db8::1": "private",
    "fec0::1": "private",
}


@pytest.mark.parametrize("addr", sorted({**FORBIDDEN_V4, **FORBIDDEN_V6}))
def test_every_forbidden_address_class_is_rejected(addr: str) -> None:
    r = FakeResolver([addr])
    code = code_of(verify_url, f"https://{HOST}/", ALLOW, r)
    assert code.startswith("address_") and code != "address_malformed", (addr, code)
    assert r.calls == [(HOST, 443)]


def test_ipv4_mapped_forms_are_refused_by_their_own_rule() -> None:
    for addr in ("::ffff:127.0.0.1", "::ffff:8.8.8.8", "::ffff:10.0.0.1"):
        assert code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver([addr])) == "address_ipv4_mapped"


def test_the_stdlib_classification_agrees_for_each_table_entry() -> None:
    for addr in {**FORBIDDEN_V4, **FORBIDDEN_V6}:
        assert forbidden_reason(ipaddress.ip_address(addr)) is not None, addr
    for addr in (PUBLIC4, PUBLIC6, "1.1.1.1", "2001:4860:4860::8888"):
        assert forbidden_reason(ipaddress.ip_address(addr)) is None, addr


@pytest.mark.parametrize(
    "bad",
    [
        "fe80::1%eth0",
        "127.1",
        "2130706433",
        "0x7f000001",
        " 8.8.8.8",
        "8.8.8.8 ",
        "example.com",
        "",
        "::ffff:",
    ],
)
def test_resolver_values_that_are_not_clean_addresses_are_rejected(bad: str) -> None:
    assert code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver([bad])) == "address_malformed"


def test_one_bad_answer_rejects_the_whole_resolution() -> None:
    assert (
        code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver([PUBLIC4, "10.0.0.1"]))
        == "address_private"
    )
    assert (
        code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver([PUBLIC6, "::1"])) == "address_loopback"
    )


def test_resolver_failures_and_wrong_shapes_are_refused() -> None:
    assert (
        code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver(OSError("no such host")))
        == "resolution_failed"
    )
    for shape in ("8.8.8.8", [], None, {PUBLIC4}, [PUBLIC4] * 17, [8]):

        class R:
            def __call__(self, h: str, p: int, shape: object = shape) -> object:
                return shape

        expected = "address_malformed" if shape == [8] else "resolution_invalid"
        assert code_of(verify_url, f"https://{HOST}/", ALLOW, R()) == expected, shape


# ---- R-c: DNS rebinding, pinning, TLS name ------------------------------------------------------------------
def test_dns_rebinding_is_defeated_because_resolution_happens_once() -> None:
    # first answer safe, any second answer forbidden: a client that resolved again at connect time would be redirected
    r = FakeResolver([PUBLIC4], ["169.254.169.254"], ["127.0.0.1"])
    v = verify_url(f"https://{HOST}/v1/search", ALLOW, r)
    assert len(r.calls) == 1  # exactly once per verification
    assert v.destination.addresses == (PUBLIC4,)
    # the pinned request carries the validated address, so the second (forbidden) answer is never consulted
    p = plan_pinned_request(v, budget(), requests_made=0)
    assert p.connect_ip == PUBLIC4
    assert len(r.calls) == 1


def test_a_rebinding_style_answer_set_in_one_response_is_rejected() -> None:
    assert (
        code_of(verify_url, f"https://{HOST}/", ALLOW, FakeResolver([PUBLIC4, "127.0.0.1"]))
        == "address_loopback"
    )


def test_each_verification_resolves_once_and_verifications_are_independent() -> None:
    r = FakeResolver([PUBLIC4], [PUBLIC6])
    a = verify_url(f"https://{HOST}/a", ALLOW, r)
    b = verify_url(f"https://{HOST}/b", ALLOW, r)
    assert len(r.calls) == 2
    assert a.destination.addresses == (PUBLIC4,) and b.destination.addresses == (PUBLIC6,)


def test_verified_destination_keeps_the_hostname_as_tls_name_and_the_ip_separately() -> None:
    v = verify_url(f"https://{HOST.upper()}:443/x", ALLOW, FakeResolver([PUBLIC4, PUBLIC6, PUBLIC4]))
    d = v.destination
    assert d.hostname == HOST and d.tls_server_hostname == HOST
    assert d.port == 443
    assert d.addresses == (PUBLIC4, PUBLIC6)  # duplicates collapsed, order kept
    assert d.tls_server_hostname not in d.addresses
    assert isinstance(d.addresses, tuple)


def test_verified_objects_are_immutable_and_cannot_be_forged() -> None:
    v = verify_url(f"https://{HOST}/x", ALLOW, FakeResolver())
    for obj, attr in (
        (v, "path_and_query"),
        (v.destination, "addresses"),
        (v.destination, "tls_server_hostname"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, attr, "x")
    with pytest.raises(TypeError):
        VerifiedDestination("evil.example", 443, ("10.0.0.1",), "evil.example")
    with pytest.raises(TypeError):
        VerifiedDestination("evil.example", 443, ("10.0.0.1",), "evil.example", object())


def test_pinned_request_plan_binds_ip_sni_and_host_header_and_has_no_redirect_switch() -> None:
    v = verify_url(f"https://{HOST}/v1/x?a=1", ALLOW, FakeResolver([PUBLIC6, PUBLIC4]))
    p = plan_pinned_request(v, budget(), requests_made=0)
    assert (p.connect_ip, p.port, p.server_hostname, p.host_header) == (PUBLIC6, 443, HOST, HOST)
    assert (p.method, p.path_and_query) == ("GET", "/v1/x?a=1")
    assert "follow_redirects" not in {f.name for f in dataclasses.fields(p)}
    allow = EgressAllowlist.of([(HOST, 8443)])
    p2 = plan_pinned_request(
        verify_url(f"https://{HOST}:8443/", allow, FakeResolver()), budget(), requests_made=0
    )
    assert p2.host_header == f"{HOST}:8443"


def test_plan_refuses_when_the_request_budget_is_spent() -> None:
    v = verify_url(f"https://{HOST}/", ALLOW, FakeResolver())
    assert plan_pinned_request(v, budget(max_requests=2), requests_made=1)
    assert (
        code_of(plan_pinned_request, v, budget(max_requests=2), requests_made=2) == "request_budget_exhausted"
    )


# ---- R-d: redirects ------------------------------------------------------------------------------------------
def redirect(location: str, status: int = 302) -> TransportResponse:
    return TransportResponse(status, (("Location", location), ("Content-Type", "text/html")))


def test_redirects_are_disabled_by_default_and_nothing_is_resolved_or_followed() -> None:
    assert budget().max_redirects == 0
    r = FakeResolver()
    loc = redirect_location(redirect(f"https://{HOST}/elsewhere"))
    assert loc == f"https://{HOST}/elsewhere"
    code = code_of(validate_redirect, loc, allowlist=ALLOW, resolver=r, budget=budget(), redirects_followed=0)
    assert code == "redirects_disabled"
    assert r.calls == []


def test_redirect_location_only_reads_a_header_for_redirect_statuses() -> None:
    assert redirect_location(TransportResponse(200, (("Location", "https://x/"),))) is None
    assert redirect_location(TransportResponse(404, ())) is None
    for status in (301, 302, 303, 307, 308):
        assert redirect_location(redirect("https://x.example/", status)) == "https://x.example/"
    assert code_of(redirect_location, TransportResponse(302, ())) == "redirect_invalid"
    assert (
        code_of(redirect_location, TransportResponse(302, (("location", "a"), ("Location", "b"))))
        == "redirect_invalid"
    )


def test_a_candidate_redirect_gets_full_independent_validation_and_a_fresh_single_resolution() -> None:
    b = budget(max_redirects=2)
    r = FakeResolver([PUBLIC4], [PUBLIC6])
    first = verify_url(f"https://{HOST}/a", ALLOW, r)
    hop = validate_redirect(f"https://{HOST}/b", allowlist=ALLOW, resolver=r, budget=b, redirects_followed=0)
    assert isinstance(hop, VerifiedUrl) and hop is not first
    assert len(r.calls) == 2  # one resolution for the request, one for the hop; no more
    assert hop.destination.addresses == (PUBLIC6,)


@pytest.mark.parametrize(
    ("loc", "code"),
    [
        (f"http://{HOST}/", "scheme_not_https"),  # https -> http downgrade
        ("/relative", "redirect_not_absolute"),
        ("//evil.example/", "redirect_not_absolute"),
        (None, "redirect_not_absolute"),
        ("https://other.example/", "host_not_allowed"),  # non-permitted host
        (f"https://{HOST}:8443/", "port_not_allowed"),
        ("https://169.254.169.254/latest/meta-data/", "ip_literal_forbidden"),  # metadata address
        ("https://[fd00:ec2::254]/", "ip_literal_forbidden"),
        (f"https://user@{HOST}/", "userinfo_forbidden"),
        (f"https://{HOST}/#x", "fragment_forbidden"),
    ],
)
def test_bad_redirect_targets_are_refused_without_resolution(loc: object, code: str) -> None:
    r = FakeResolver()
    assert (
        code_of(
            validate_redirect,
            loc,
            allowlist=ALLOW,
            resolver=r,
            budget=budget(max_redirects=3),
            redirects_followed=0,
        )
        == code
    )
    assert r.calls == []


def test_redirect_to_an_allowed_name_that_resolves_to_a_forbidden_address_is_refused() -> None:
    r = FakeResolver(["169.254.169.254"])
    c = code_of(
        validate_redirect,
        f"https://{HOST}/x",
        allowlist=ALLOW,
        resolver=r,
        budget=budget(max_redirects=1),
        redirects_followed=0,
    )
    assert c == "address_link_local"
    assert len(r.calls) == 1


def test_redirect_count_is_bounded() -> None:
    b = budget(max_redirects=2)
    ok = dict(allowlist=ALLOW, resolver=FakeResolver(), budget=b)
    validate_redirect(f"https://{HOST}/x", redirects_followed=1, **ok)  # type: ignore[arg-type]
    assert code_of(validate_redirect, f"https://{HOST}/x", redirects_followed=2, **ok) == "too_many_redirects"


# ---- R-e: budgets --------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad",
    [
        {"max_requests": 0},
        {"max_requests": -1},
        {"max_requests": 51},
        {"max_requests": 1.5},
        {"max_requests": True},
        {"max_requests": "5"},
        {"connect_timeout_s": 0},
        {"connect_timeout_s": -1},
        {"connect_timeout_s": 31},
        {"connect_timeout_s": float("nan")},
        {"connect_timeout_s": float("inf")},
        {"connect_timeout_s": True},
        {"connect_timeout_s": None},
        {"read_timeout_s": 0},
        {"read_timeout_s": -0.1},
        {"read_timeout_s": 30.5},
        {"total_timeout_s": 0},
        {"total_timeout_s": -5},
        {"total_timeout_s": 1801},
        {"total_timeout_s": 5},  # below read (10)
        {"max_response_bytes": 0},
        {"max_response_bytes": -1},
        {"max_response_bytes": 20 * 1024 * 1024 + 1},
        {"max_response_bytes": 1.0},
        {"max_response_bytes": False},
        {"max_redirects": -1},
        {"max_redirects": 4},
        {"max_redirects": 1.0},
    ],
)
def test_budgets_reject_zero_negative_and_out_of_range_values(bad: dict[str, object]) -> None:
    assert code_of(budget, **bad) == "budget_invalid"


def test_budget_boundaries_are_accepted_and_the_value_is_immutable() -> None:
    b = RequestBudget(50, 30, 30, 1800, 20 * 1024 * 1024, 3)
    assert b.max_requests == 50 and b.max_redirects == 3
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.max_requests = 51  # type: ignore[misc]
    with pytest.raises(TypeError):
        RequestBudget(1, 1, 1, 1)  # type: ignore[call-arg]  # no implicit defaults except max_redirects


def test_budget_checks_are_pure() -> None:
    b = budget(max_requests=2, max_response_bytes=100)
    require_request_allowed(b, 0)
    require_request_allowed(b, 1)
    assert code_of(require_request_allowed, b, 2) == "request_budget_exhausted"
    assert code_of(require_request_allowed, b, -1) == "budget_invalid"
    require_response_size(b, 100)
    assert code_of(require_response_size, b, 101) == "response_too_large"
    assert code_of(require_response_size, b, -1) == "budget_invalid"
