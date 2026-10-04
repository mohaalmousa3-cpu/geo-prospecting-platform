"""Offline fixture connector over committed *synthetic* fixtures.

Fixtures are plain JSON files in `geo_connectors/fixtures/`. They are invented for tests, are
labelled `"synthetic": true` and do not describe any real catalogue. The connector reads a local file only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from geo_connectors import __version__
from geo_connectors.contracts import CatalogRecord, Connector, FetchContext, FetchResult, SourceMetadata
from geo_connectors.errors import ConnectorRequestError, FixtureError

FIXTURE_DIR = Path(__file__).parent / "fixtures"
_NAME = re.compile(r"^[a-z0-9_]{1,64}$")
_REQUIRED = ("fixture_format", "synthetic", "dataset", "dataset_version", "generated_at", "items")


def _bbox_of_polygon(geojson: Any) -> tuple[float, float, float, float]:
    try:
        ring = geojson["coordinates"][0]
        xs = [float(p[0]) for p in ring]
        ys = [float(p[1]) for p in ring]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ConnectorRequestError("aoi_geojson is not a usable Polygon") from exc
    if not xs:
        raise ConnectorRequestError("aoi_geojson has an empty ring")
    return min(xs), min(ys), max(xs), max(ys)


def _intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def load_fixture(name: str, directory: Path = FIXTURE_DIR) -> dict[str, Any]:
    """Load and validate a fixture. The name is a bare identifier: no separators, no traversal."""
    if not _NAME.fullmatch(name):
        raise FixtureError(f"invalid fixture name {name!r}")
    path = directory / f"{name}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FixtureError(f"fixture {name!r} not found") from None
    except ValueError as exc:
        raise FixtureError(f"fixture {name!r} is not valid JSON") from exc
    if not isinstance(doc, dict) or any(k not in doc for k in _REQUIRED):
        raise FixtureError(f"fixture {name!r} lacks required keys {_REQUIRED}")
    if doc["synthetic"] is not True:
        raise FixtureError(f"fixture {name!r} is not labelled synthetic")
    if doc["fixture_format"] != 1 or not isinstance(doc["items"], list):
        raise FixtureError(f"fixture {name!r} has an unsupported format")
    ids = [i.get("id") for i in doc["items"]]
    if len(ids) != len(set(ids)) or not all(isinstance(i, str) and i for i in ids):
        raise FixtureError(f"fixture {name!r} has missing or duplicate item ids")
    return doc


class FixtureConnector(Connector):
    name = "fixture"

    def _fetch(self, ctx: FetchContext) -> FetchResult:
        doc = load_fixture(ctx.fixture_name)
        aoi_bbox = _bbox_of_polygon(ctx.aoi_geojson)
        matched: list[CatalogRecord] = []
        for it in doc["items"]:
            acquired = datetime.fromisoformat(str(it["datetime"]).replace("Z", "+00:00"))
            bbox = tuple(float(v) for v in it["bbox"])
            if (
                it["collection"] in ctx.collections
                and ctx.start <= acquired.date() <= ctx.end
                and len(bbox) == 4
                and _intersects(bbox, aoi_bbox)
            ):
                matched.append(
                    CatalogRecord(
                        item_id=it["id"],
                        collection=it["collection"],
                        acquired=str(it["datetime"]),
                        bbox=bbox,
                        properties=dict(it.get("properties", {})),
                    )
                )
        matched.sort(key=lambda r: (r.acquired, r.item_id))
        return FetchResult(
            records=tuple(matched[: ctx.max_items]),
            truncated=len(matched) > ctx.max_items,
            source=SourceMetadata(
                connector=self.name,
                kind="fixture",
                dataset=str(doc["dataset"]),
                dataset_version=str(doc["dataset_version"]),
                retrieved_at=str(doc["generated_at"]),
                parameters={
                    "fixture": ctx.fixture_name,
                    "collections": list(ctx.collections),
                    "start": ctx.start.isoformat(),
                    "end": ctx.end.isoformat(),
                    "max_items": ctx.max_items,
                    "aoi_bbox": list(aoi_bbox),
                },
                code_version=__version__,
                synthetic=True,
            ),
        )
