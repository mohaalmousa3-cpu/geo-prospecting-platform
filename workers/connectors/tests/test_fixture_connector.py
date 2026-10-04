from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from helpers import ctx

from geo_connectors.errors import FixtureError
from geo_connectors.fixture import FIXTURE_DIR, FixtureConnector, load_fixture
from geo_connectors.testing import assert_connector_contract


def test_contract_suite_passes() -> None:
    res = assert_connector_contract(FixtureConnector(), ctx())
    assert res.records and res.source.synthetic and res.source.kind == "fixture"


def test_filters_by_collection_window_and_footprint() -> None:
    res = FixtureConnector().fetch(ctx(collections=("synthetic-optical",)))
    assert all(r.collection == "synthetic-optical" for r in res.records)
    assert "SYNTH-A-FAR" not in {r.item_id for r in res.records}  # footprint far from the AOI
    narrow = FixtureConnector().fetch(ctx(start=date(2026, 1, 1), end=date(2026, 1, 31)))
    assert all(r.acquired.startswith("2026-01") for r in narrow.records)
    radar = FixtureConnector().fetch(ctx(collections=("synthetic-radar",)))
    assert [r.item_id for r in radar.records] == ["SYNTH-B-0001"]


def test_max_items_truncates_and_reports_it() -> None:
    all_ = FixtureConnector().fetch(ctx(max_items=20))
    cut = FixtureConnector().fetch(ctx(max_items=3))
    assert len(cut.records) == 3 and cut.truncated and not all_.truncated
    assert cut.records == all_.records[:3]


def test_zero_results_is_an_empty_result_not_an_error() -> None:
    res = FixtureConnector().fetch(ctx(fixture_name="synthetic_catalog_empty_v1"))
    assert res.records == () and res.truncated is False and res.source.synthetic
    assert_connector_contract(FixtureConnector(), ctx(fixture_name="synthetic_catalog_empty_v1"))


def test_source_metadata_records_parameters_and_versions() -> None:
    s = FixtureConnector().fetch(ctx()).source
    assert s.dataset == "synthetic-catalog-fixture" and s.dataset_version == "1"
    assert s.parameters["fixture"] == "synthetic_catalog_v1" and s.parameters["max_items"] == 20
    assert s.retrieved_at == "2026-10-05T00:00:00Z"  # the fixture's own date: deterministic, not "now"


@pytest.mark.parametrize("name", ["../x", "a/b", "A", "", "x.json", "a" * 65, "..\\x"])
def test_fixture_names_cannot_traverse(name: str) -> None:
    with pytest.raises(FixtureError):
        load_fixture(name)


def test_missing_fixture_is_an_error() -> None:
    with pytest.raises(FixtureError, match="not found"):
        load_fixture("does_not_exist")


def _write(tmp: Path, doc: object) -> None:
    (tmp / "f.json").write_text(json.dumps(doc))


def _good() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "synthetic_catalog_v1.json").read_text())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(synthetic=False),
        lambda d: d.pop("dataset"),
        lambda d: d.update(fixture_format=2),
        lambda d: d.update(items=[{"id": "x"}, {"id": "x"}]),
        lambda d: d.update(items=[{"id": ""}]),
    ],
)
def test_malformed_or_unlabelled_fixtures_are_rejected(tmp_path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    doc = _good()
    mutate(doc)
    _write(tmp_path, doc)
    with pytest.raises(FixtureError):
        load_fixture("f", directory=tmp_path)
    (tmp_path / "f.json").write_text("{not json")
    with pytest.raises(FixtureError, match="JSON"):
        load_fixture("f", directory=tmp_path)


def test_committed_fixtures_are_all_valid_and_synthetic() -> None:
    files = sorted(FIXTURE_DIR.glob("*.json"))
    assert files
    for f in files:
        assert load_fixture(f.stem)["synthetic"] is True
