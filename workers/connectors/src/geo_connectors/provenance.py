"""Provenance record of a staged asset (CLAUDE.md §4.6: dataset, version, date, parameters, code version).

Extracted unchanged from the handler (Phase 3a closure). Pure: no I/O, no scientific content. The record
describes where catalogue metadata came from; it carries no confidence, score or interpretation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from geo_connectors.contracts import SourceMetadata


def build_provenance_record(
    *, kind: str, job_id: UUID, asset_id: UUID, request_hash: str, source: SourceMetadata
) -> dict[str, Any]:
    """The JSON stored in `provenance.record` for one asset (ids as strings; `source` as a plain dict)."""
    return {
        "kind": kind,
        "job_id": str(job_id),
        "asset_id": str(asset_id),
        "request_hash": request_hash,
        "source": asdict(source),
    }
