from __future__ import annotations

from datetime import date

from geo_connectors.contracts import FetchContext

# A small square near the synthetic fixture footprints (arbitrary coordinates; the fixtures are invented).
AOI = {
    "type": "Polygon",
    "coordinates": [[[10.0, 40.0], [10.1, 40.0], [10.1, 40.1], [10.0, 40.1], [10.0, 40.0]]],
}


def ctx(**kw: object) -> FetchContext:
    base: dict[str, object] = {
        "aoi_geojson": AOI,
        "start": date(2026, 1, 1),
        "end": date(2026, 12, 31),
        "collections": ("synthetic-optical",),
        "max_items": 20,
        "max_window_days": 365,
    }
    base.update(kw)
    return FetchContext(**base)  # type: ignore[arg-type]
