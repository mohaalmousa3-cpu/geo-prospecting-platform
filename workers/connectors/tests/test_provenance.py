"""The named provenance helper keeps the behaviour the handler had inline (golden structure, direct tests)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from db_helpers import PAYLOAD, context, fixture_aoi, running_job, settings_for
from sqlalchemy import Engine, text

from geo_common.storage import LocalStorage
from geo_connectors.contracts import FetchContext, SourceMetadata
from geo_connectors.handler import run_catalog_search
from geo_connectors.provenance import build_provenance_record
from geo_connectors.registry import resolve_connector

JOB, ASSET = uuid.UUID(int=1), uuid.UUID(int=2)
SOURCE = SourceMetadata(
    connector="fixture", kind="fixture", dataset="d", dataset_version="1", retrieved_at="2026-10-05T00:00:00Z",
    parameters={"a": [1, 2]}, code_version="0.1.0", synthetic=True,
)  # fmt: skip


def test_golden_structure_and_types() -> None:
    rec = build_provenance_record(
        kind="scene_catalog", job_id=JOB, asset_id=ASSET, request_hash="v1:" + "a" * 64, source=SOURCE
    )
    assert rec == {
        "kind": "scene_catalog",
        "job_id": str(JOB),
        "asset_id": str(ASSET),
        "request_hash": "v1:" + "a" * 64,
        "source": {
            "connector": "fixture", "kind": "fixture", "dataset": "d", "dataset_version": "1",
            "retrieved_at": "2026-10-05T00:00:00Z", "parameters": {"a": [1, 2]}, "code_version": "0.1.0",
            "synthetic": True,
        },
    }  # fmt: skip
    assert list(rec) == [
        "kind",
        "job_id",
        "asset_id",
        "request_hash",
        "source",
    ]  # key order is part of the record
    json.dumps(rec)  # plain JSON types only


def test_it_is_pure_and_carries_no_result_vocabulary() -> None:
    a = build_provenance_record(kind="k", job_id=JOB, asset_id=ASSET, request_hash="h", source=SOURCE)
    b = build_provenance_record(kind="k", job_id=JOB, asset_id=ASSET, request_hash="h", source=SOURCE)
    assert a == b and a is not b
    flat = json.dumps(a).lower()
    assert not any(w in flat for w in ("confidence", "uncertainty", "score", "probab"))


def test_source_fields_are_exactly_the_connectors_source_metadata() -> None:
    c = resolve_connector("fixture", "fixture")
    ctx = FetchContext(
        {"type": "Polygon", "coordinates": [[[10.02, 40.02], [10.05, 40.02], [10.05, 40.05], [10.02, 40.02]]]},
        date(2026, 1, 1), date(2026, 12, 31), ("synthetic-optical",), 20, 365,
    )  # fmt: skip
    rec = build_provenance_record(
        kind="k", job_id=JOB, asset_id=ASSET, request_hash="h", source=c.fetch(ctx).source
    )
    assert set(rec["source"]) == {
        "connector", "kind", "dataset", "dataset_version", "retrieved_at", "parameters", "code_version", "synthetic",
    }  # fmt: skip


@pytest.mark.integration
def test_the_stored_provenance_equals_the_helper_output(
    engine: Engine, storage: LocalStorage, tmp_path: Path
) -> None:
    _, a = fixture_aoi(engine)
    job = running_job(engine, a)
    out = run_catalog_search(
        PAYLOAD, context(job), engine=engine, storage=storage, settings=settings_for(tmp_path)
    )
    assert out.status == "succeeded"
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT p.record, a.id, a.request_hash FROM data_asset a JOIN provenance p ON p.id = a.provenance_id"
            )
        ).one()
    stored = row.record
    rebuilt = build_provenance_record(
        kind="scene_catalog", job_id=job, asset_id=row.id, request_hash=row.request_hash,
        source=SourceMetadata(**{**stored["source"]}),
    )  # fmt: skip
    assert stored == rebuilt
