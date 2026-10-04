"""Reusable offline contract checks for any `Connector` (fixture harness, P3-08).

Plain assertions (no pytest import) so the same checks run in unit tests of every future connector.
"""

from __future__ import annotations

from datetime import date, datetime

from geo_connectors.contracts import Connector, FetchContext, FetchResult

# Catalogue records are metadata: these keys would turn them into something that looks like a finding.
FORBIDDEN_PROPERTY_KEYS = frozenset({"confidence", "uncertainty", "score", "probability", "interpretation"})


def assert_connector_contract(connector: Connector, ctx: FetchContext) -> FetchResult:
    first = connector.fetch(ctx)
    second = connector.fetch(ctx)
    assert first == second, "fetch must be deterministic for identical input"
    assert len(first.records) <= ctx.max_items, "fetch must honour max_items"
    ids = [r.item_id for r in first.records]
    assert len(ids) == len(set(ids)), "record ids must be unique"
    assert first.records == tuple(sorted(first.records, key=lambda r: (r.acquired, r.item_id))), (
        "records must be ordered"
    )
    for r in first.records:
        assert r.collection in ctx.collections
        assert ctx.start <= _date(r.acquired) <= ctx.end
        assert not FORBIDDEN_PROPERTY_KEYS & {k.lower() for k in r.properties}, (
            "records must not carry scientific-looking fields"
        )
    s = first.source
    for field in ("connector", "kind", "dataset", "dataset_version", "retrieved_at", "code_version"):
        assert getattr(s, field), f"source.{field} must be set"
    assert s.parameters, "source.parameters must be recorded"
    if s.kind == "fixture":
        assert s.synthetic is True, "fixture data must be labelled synthetic"
    return first


def _date(iso: str) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
