"""T9 — scientific guards for the Phase 3a connector outputs (fixtures only).

Catalogue records and staged assets are *inputs*: no confidence, score, uncertainty, probability, prospectivity,
anomaly, depth or any interpretation, and no `result` row or envelope (ADR-0014 §2; CLAUDE.md §4). These tests
pin the *shape* of what Phase 3a can emit, so a new field has to be added to an allow-list on purpose.

Limits (do not over-read a pass): they check declared names and committed fixtures, not the meaning of free-text
values, and not run-time strings the code assembles. The end-to-end flow test checks the real output of a job.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest

from forbidden_terms import is_scanned
from geo_common.config import Settings
from geo_connectors.contracts import CatalogRecord, FetchResult, SourceMetadata

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "workers/connectors/src/geo_connectors/fixtures"
# Names that would make an input look like a finding. A match in a declared field/property name fails the test.
RESULT_VOCABULARY = re.compile(
    r"confidence|uncertainty|score|probab|prospectiv|anomal|depth|rank|grade|likelihood|target_?quality|"
    r"validat(ed|ion)_?status|envelope|interpretation|void_evidence|gold_",
    re.I,
)


def test_the_forbidden_term_scan_reads_the_phase_3a_code_and_fixtures() -> None:
    expected = [
        *ROOT.glob("workers/connectors/src/geo_connectors/**/*.py"),
        *FIXTURES.glob("*.json"),
        ROOT / "apps/backend/src/app/catalog_jobs.py",
        ROOT / "apps/backend/src/app/api/assets.py",
        ROOT / "packages/pycommon/src/geo_common/assets_pg.py",
        ROOT / "packages/pycommon/src/geo_common/migrations/versions/0005_data_asset.py",
        ROOT / "scripts/image_smoke_client.py",
        ROOT / "scripts/image_smoke_import.py",
        ROOT / "scripts/image_smoke.sh",
        ROOT / "infrastructure/docker/docker-compose.smoke.yml",
        ROOT / "packages/schemas/geo-contracts.schema.json",
    ]
    assert len(expected) > 15
    unread = [p.relative_to(ROOT).as_posix() for p in expected if not p.exists() or not is_scanned(ROOT, p)]
    assert unread == [], f"not covered by the forbidden-term scan: {unread}"


def _names(cls: Any) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def test_catalogue_record_source_and_fetch_result_shapes_are_allow_listed() -> None:
    assert _names(CatalogRecord) == {"item_id", "collection", "acquired", "bbox", "properties"}
    assert _names(SourceMetadata) == {
        "connector",
        "kind",
        "dataset",
        "dataset_version",
        "retrieved_at",
        "parameters",
        "code_version",
        "synthetic",
    }
    assert _names(FetchResult) == {"records", "source", "truncated"}
    for cls in (CatalogRecord, SourceMetadata, FetchResult):
        assert not [n for n in _names(cls) if RESULT_VOCABULARY.search(n)], cls.__name__


def test_committed_fixtures_are_synthetic_catalogue_metadata_only() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert {f.name for f in files} == {"synthetic_catalog_empty_v1.json", "synthetic_catalog_v1.json"}
    for f in files:
        doc = json.loads(f.read_text())
        assert doc["synthetic"] is True, f.name
        assert set(doc) == {
            "fixture_format",
            "synthetic",
            "dataset",
            "dataset_version",
            "generated_at",
            "description",
            "items",
        }, f.name
        for item in doc["items"]:
            assert set(item) == {"id", "collection", "datetime", "bbox", "properties"}, item["id"]
            assert set(item["properties"]) <= {"platform", "cloud_cover_percent"}, item["id"]
            assert item["properties"].get("platform", "SYNTH").startswith("SYNTH"), item["id"]


def _props(node: Any) -> set[str]:
    """Every property name anywhere inside an OpenAPI schema fragment."""
    out: set[str] = set()
    if isinstance(node, dict):
        out |= set(node.get("properties", {}))
        for v in node.values():
            out |= _props(v)
    elif isinstance(node, list):
        for v in node:
            out |= _props(v)
    return out


@pytest.fixture(scope="module")
def schemas() -> dict[str, Any]:
    from app.main import create_app

    settings = Settings(_env_file=None, CORS_ALLOWED_ORIGINS="http://localhost:3000")  # type: ignore[call-arg]
    spec = create_app(settings, engine=object()).openapi()  # type: ignore[arg-type]
    return dict(spec["components"]["schemas"])


def test_job_and_asset_api_schemas_are_allow_listed_and_free_of_result_vocabulary(
    schemas: dict[str, Any],
) -> None:
    assert set(schemas["Job"]["properties"]) == {
        "id", "type", "aoi_id", "project_id", "status", "priority", "attempts", "max_attempts",
        "cancel_requested", "error", "created_at", "started_at", "finished_at",
    }  # fmt: skip
    assert set(schemas["JobCreate"]["properties"]) == {"type", "aoi_id", "payload"}  # no project_id
    assert set(schemas["Asset"]["properties"]) == {
        "id", "project_id", "aoi_id", "job_id", "kind", "media_type", "size_bytes", "sha256", "created_at",
        "provenance",
    }  # fmt: skip
    assert set(schemas["AssetDeleted"]["properties"]) == {"deleted", "files_pending_cleanup"}
    for name in ("Job", "JobCreate", "Asset", "AssetList", "AssetDeleted"):
        assert not [p for p in _props(schemas[name]) if RESULT_VOCABULARY.search(p)], name
        if name in ("Job", "Asset", "AssetDeleted"):  # unknown keys are rejected by the contract
            assert schemas[name].get("additionalProperties") is False, name


def test_the_contract_schema_rejects_unknown_asset_and_job_keys() -> None:
    doc = json.loads((ROOT / "packages/schemas/geo-contracts.schema.json").read_text())
    for name in ("Asset", "Job", "AssetDeleted"):
        assert doc["definitions"][name]["additionalProperties"] is False, name
    assert doc["definitions"]["JobType"]["enum"] == ["noop", "catalog_search"]
    assert doc["definitions"]["AssetKind"]["enum"] == ["scene_catalog", "dem_clip", "user_vector"]


def test_connector_mode_is_disabled_by_default_and_nothing_enables_live() -> None:
    assert Settings(_env_file=None).CONNECTOR_MODE == "disabled"  # type: ignore[call-arg]
    env = (ROOT / ".env.example").read_text()
    assert "\nCONNECTOR_MODE=disabled\n" in env
    for rel in ("infrastructure/docker/docker-compose.yml", ".github/workflows/ci.yml", "Makefile"):
        assert not re.search(r"CONNECTOR_MODE\W+live", (ROOT / rel).read_text()), rel
    smoke = (ROOT / "infrastructure/docker/docker-compose.smoke.yml").read_text()
    assert set(re.findall(r"CONNECTOR_MODE:\s*(\w+)", smoke)) == {"fixture"}  # the only non-default, fixtures
