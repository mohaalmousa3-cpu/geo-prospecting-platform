"""The fixed-query representation accepts a registered name and nothing else (Phase 3b R8, offline)."""

from __future__ import annotations

import dataclasses

import pytest

from geo_connectors.egress_policy import EgressPolicyError, ensure_relative_path
from geo_connectors.fixed_query import (
    APPROVED_FOR_EXECUTION,
    STATUS_LABEL,
    FixedQuery,
    fixed_query,
    fixed_query_names,
    from_mapping,
)


def code_of(raw: object) -> str:
    with pytest.raises(EgressPolicyError) as e:
        from_mapping(raw)
    return e.value.code


def test_registered_names_build_and_are_labelled_not_authorised() -> None:
    assert fixed_query_names() == ("collection_metadata", "search_probe")
    assert APPROVED_FOR_EXECUTION is False
    for n in fixed_query_names():
        q = from_mapping({"name": n})
        assert q == fixed_query(n) and q.method == "GET"
        assert q.label == STATUS_LABEL and "not authorized to execute" in q.label
        assert ensure_relative_path(q.path_and_query) == q.path_and_query


def test_queries_hold_no_host_scheme_credential_or_project_value() -> None:
    for n in fixed_query_names():
        q = fixed_query(n)
        text = (q.name + q.path_and_query).lower()
        assert "://" not in text and "@" not in text and "token" not in text
        assert q.path_and_query.startswith("/v1/")
        assert not hasattr(q, "headers") and not hasattr(q, "host") and not hasattr(q, "aoi_id")
        assert {f.name for f in dataclasses.fields(q)} == {"name", "method", "path_and_query"}


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("aoi_id", "fixed_query_aoi_or_project"),
        ("aoi", "fixed_query_aoi_or_project"),
        ("project_id", "fixed_query_aoi_or_project"),
        ("project", "fixed_query_aoi_or_project"),
        ("geometry", "fixed_query_aoi_or_project"),
        ("intersects", "fixed_query_aoi_or_project"),
        ("coordinates", "fixed_query_aoi_or_project"),
        ("latitude", "fixed_query_aoi_or_project"),
        ("bbox", "fixed_query_bbox"),
        ("BBox", "fixed_query_bbox"),
        ("datetime", "fixed_query_datetime"),
        ("start", "fixed_query_datetime"),
        ("end_date", "fixed_query_datetime"),
        ("cookie", "fixed_query_cookie"),
        ("Cookies", "fixed_query_cookie"),
        ("authorization", "fixed_query_credential"),
        ("Authorization", "fixed_query_credential"),
        ("token", "fixed_query_credential"),
        ("api-key", "fixed_query_credential"),
        ("password", "fixed_query_credential"),
        ("headers", "fixed_query_header"),
        ("User-Agent", "fixed_query_header"),
        ("x_header", "fixed_query_header"),
        ("path", "fixed_query_endpoint"),
        ("url", "fixed_query_endpoint"),
        ("endpoint", "fixed_query_endpoint"),
        ("href", "fixed_query_endpoint"),
        ("host", "fixed_query_endpoint"),
        ("method", "fixed_query_endpoint"),
        ("collections", "fixed_query_unknown_field"),
        ("limit", "fixed_query_unknown_field"),
        ("NAME", "fixed_query_unknown_field"),
        ("extra", "fixed_query_unknown_field"),
    ],
)
def test_every_non_name_field_is_rejected_with_its_class(field: str, code: str) -> None:
    assert code_of({"name": "search_probe", field: "x"}) == code
    assert code_of({field: "x"}) == code  # also without a name


def test_forbidden_values_are_never_echoed_back() -> None:
    with pytest.raises(EgressPolicyError) as e:
        from_mapping({"name": "search_probe", "cookie": "SECRET-VALUE-123"})
    assert "SECRET-VALUE-123" not in str(e.value)


@pytest.mark.parametrize("bad", [None, [], "search_probe", ("name", "x"), 5])
def test_non_mapping_input_is_refused(bad: object) -> None:
    assert code_of(bad) == "fixed_query_not_a_mapping"


@pytest.mark.parametrize(
    "name", [None, 5, "", "SEARCH_PROBE", "../etc/passwd", "https://x/", "search_probe ", ["search_probe"]]
)
def test_unknown_or_non_string_names_are_refused(name: object) -> None:
    assert code_of({"name": name}) == "fixed_query_unknown_name"
    assert code_of({}) == "fixed_query_unknown_name"


def test_arbitrary_endpoint_paths_cannot_be_constructed_directly() -> None:
    for args in (
        ("x", "GET", "/anything"),
        ("search_probe", "GET", "/v1/evil"),
        ("search_probe", "POST", "/v1/search"),
        ("collection_metadata", "GET", "https://evil.example/"),
    ):
        with pytest.raises(EgressPolicyError) as e:
            FixedQuery(*args)
        assert e.value.code == "fixed_query_not_registered"


def test_a_registered_query_is_immutable() -> None:
    q = fixed_query("collection_metadata")
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.path_and_query = "/other"  # type: ignore[misc]
