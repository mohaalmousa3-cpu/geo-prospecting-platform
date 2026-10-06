"""Canonical, versioned identity of an asset publication request (idempotency only).

This is **not** scientific-result deduplication. It lets a retried job recognise that the asset it is about
to publish was already published for the same job and request (`UNIQUE (job_id, kind, request_hash)` for
job-bound assets).

Version 1 (stored as ``v1:<64 lowercase hex>``):

* Canonical input: a JSON object with exactly these members: ``v`` (=1), ``kind``, ``connector`` (name),
  ``connector_version`` (package version), ``dataset``, ``dataset_version``, ``fixture`` (fixture identity),
  ``aoi`` (the GeoJSON Polygon, coordinates as floats), ``collections`` (sorted, de-duplicated), ``start`` and
  ``end`` (ISO dates), ``max_items``.
* Not included: job id, worker, timestamps (including ``retrieved_at``), record contents.
* Serialisation: ``json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
  allow_nan=False)`` encoded as UTF-8 (floats use Python's shortest round-trip form).
* Digest: SHA-256, lowercase hexadecimal, prefixed with ``v<version>:``.
* Versioning: any change of the member list, serialisation or digest increments ``REQUEST_HASH_VERSION``;
  the prefix then differs, so values of different versions never compare equal (idempotency does not span
  versions). A connector package version change also changes the identity on purpose: a different
  implementation is a different request.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from geo_connectors.contracts import FetchContext, SourceMetadata

REQUEST_HASH_VERSION = 1


def _floats(value: Any) -> Any:
    if isinstance(value, list | tuple):
        return [_floats(v) for v in value]
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return value


def canonical_request(kind: str, ctx: FetchContext, source: SourceMetadata) -> bytes:
    obj = {
        "v": REQUEST_HASH_VERSION,
        "kind": kind,
        "connector": source.connector,
        "connector_version": source.code_version,
        "dataset": source.dataset,
        "dataset_version": source.dataset_version,
        "fixture": ctx.fixture_name,
        "aoi": {"type": ctx.aoi_geojson["type"], "coordinates": _floats(ctx.aoi_geojson["coordinates"])},
        "collections": sorted(set(ctx.collections)),
        "start": ctx.start.isoformat(),
        "end": ctx.end.isoformat(),
        "max_items": ctx.max_items,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def request_hash(kind: str, ctx: FetchContext, source: SourceMetadata) -> str:
    return f"v{REQUEST_HASH_VERSION}:{hashlib.sha256(canonical_request(kind, ctx, source)).hexdigest()}"
