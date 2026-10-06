"""Runs INSIDE the worker image (`docker run --network none`): every registered handler loads, and the
fixture connector answers from the committed synthetic fixtures. No database, no network."""

from __future__ import annotations

import json
from datetime import date

from geo_connectors.contracts import FetchContext
from geo_connectors.registry import resolve_connector
from runner.handlers import DEFAULT_HANDLERS, load_handler

loaded = {}
for name, path in DEFAULT_HANDLERS.items():
    fn = load_handler(path)
    assert callable(fn), name
    loaded[name] = path
assert "catalog_search" in loaded, "the fixtures-only handler must be registered"

aoi = {"type": "Polygon", "coordinates": [[[10.02, 40.02], [10.05, 40.02], [10.05, 40.05], [10.02, 40.02]]]}
res = resolve_connector("fixture", "fixture").fetch(
    FetchContext(aoi, date(2026, 1, 1), date(2026, 12, 31), ("synthetic-optical",), 20, 365)
)
assert res.records and res.source.synthetic is True, "the committed fixtures must be inside the image"
print(json.dumps({"handlers": loaded, "fixture_records": len(res.records), "synthetic": True}))
