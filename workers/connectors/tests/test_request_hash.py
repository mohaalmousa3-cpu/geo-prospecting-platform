"""Canonical, versioned request identity (idempotency only; see geo_connectors.request_hash)."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

import pytest
from helpers import ctx

from geo_connectors.contracts import FetchContext, SourceMetadata
from geo_connectors.request_hash import REQUEST_HASH_VERSION, canonical_request, request_hash

SRC = SourceMetadata(
    "fixture", "fixture", "synthetic-catalog-fixture", "1", "2026-10-05T00:00:00Z", {"x": 1}, "0.1.0", True
)


def h(c: FetchContext | None = None, s: SourceMetadata = SRC) -> str:
    return request_hash("scene_catalog", c or ctx(), s)


def test_format_version_and_determinism() -> None:
    v = h()
    assert re.fullmatch(r"v1:[0-9a-f]{64}", v) and REQUEST_HASH_VERSION == 1 and v == h()


def test_golden_value_pins_the_v1_definition() -> None:
    # Any change of the canonical input, serialisation or digest must bump REQUEST_HASH_VERSION and this value.
    assert canonical_request("scene_catalog", ctx(), SRC).startswith(b'{"aoi":{"coordinates":[[[10.0,40.0],')
    assert h() == "v1:0b37ee02a35aa88bc115ceaa9617cfc58d043277bd4714a643703117bbbfbb01"


def test_every_identity_field_changes_the_hash() -> None:
    base = h()
    variants = {
        "kind": request_hash("dem_clip", ctx(), SRC),
        "connector": h(s=replace(SRC, connector="other")),
        "connector_version": h(s=replace(SRC, code_version="9.9.9")),
        "dataset": h(s=replace(SRC, dataset="another")),
        "dataset_version": h(s=replace(SRC, dataset_version="2")),
        "fixture": h(ctx(fixture_name="synthetic_catalog_empty_v1")),
        "aoi": h(ctx(aoi_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]})),
        "collections": h(ctx(collections=("synthetic-radar",))),
        "start": h(ctx(start=date(2026, 1, 2))),
        "end": h(ctx(end=date(2026, 12, 30))),
        "max_items": h(ctx(max_items=19)),
    }
    assert all(v != base for v in variants.values()) and len(set(variants.values())) == len(variants)


def test_incidental_representation_does_not_change_the_hash() -> None:
    base = h()
    assert h(ctx(collections=("synthetic-optical", "synthetic-optical"))) == base  # de-duplicated
    ints = {"type": "Polygon", "coordinates": [[[10, 40], [10.1, 40], [10.1, 40.1], [10, 40.1], [10, 40]]]}
    floats = {
        "type": "Polygon",
        "coordinates": [[[10.0, 40.0], [10.1, 40.0], [10.1, 40.1], [10.0, 40.1], [10.0, 40.0]]],
    }
    assert h(ctx(aoi_geojson=ints)) == h(ctx(aoi_geojson=floats)) == base
    two = ctx(collections=("b", "a"))
    assert h(two) == h(ctx(collections=("a", "b")))


@pytest.mark.parametrize("field", ["retrieved_at", "parameters", "synthetic"])
def test_non_identity_source_fields_are_excluded(field: str) -> None:
    changed = {"retrieved_at": "2030-01-01T00:00:00Z", "parameters": {"y": 2}, "synthetic": False}[field]
    assert h(s=replace(SRC, **{field: changed})) == h()


def test_the_version_prefix_prevents_cross_version_equality() -> None:
    assert h().startswith("v1:") and not h().startswith("v2:")
