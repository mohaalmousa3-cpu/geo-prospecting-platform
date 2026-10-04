"""AOI persistence (PostgreSQL/PostGIS). Geometry is stored as Polygon, SRID 4326."""

# ruff: noqa: S608  (f-strings interpolate only the module constant _FULL; all values are bound)

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from app.aoi.service import Draft

_ADVISORY_KEY = 7_000_002  # serialises count+insert so MAX_STORED_AOIS cannot be overshot


class AoiLimitReachedError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"AOI storage limit reached: MAX_STORED_AOIS={limit}")
        self.limit = limit


_FULL = (
    "id, name, source AS method, ST_AsGeoJSON(geom, 9)::jsonb AS geometry, "
    "ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] AS bbox, "
    "area_km2, vertex_count, working_crs, details, created_at"
)


def _row(m: Any) -> dict[str, Any]:
    d = dict(m)
    d["warnings"] = []
    return d


class AoiRepository:
    def __init__(self, engine: Engine, max_stored: int) -> None:
        self._engine = engine
        self._max = max_stored

    def create(self, name: str, draft: Draft) -> dict[str, Any]:
        g = draft.geom
        details = {**draft.details}
        with self._engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_KEY})
            if conn.execute(text("SELECT count(*) FROM aoi")).scalar_one() >= self._max:
                raise AoiLimitReachedError(self._max)
            row = conn.execute(
                text(
                    "INSERT INTO aoi (name, geom, source, area_km2, vertex_count, working_crs, details) "
                    "VALUES (:n, ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326), :s, :a, :v, :c, "
                    "CAST(:d AS jsonb)) "
                    f"RETURNING {_FULL}"
                ),
                {
                    "n": name,
                    "g": json.dumps(g.geojson()),
                    "s": draft.method,
                    "a": g.area_km2,
                    "v": g.vertex_count,
                    "c": g.working_crs,
                    "d": json.dumps(details),
                },
            ).one()
        out = _row(row._mapping)
        out["warnings"] = g.warnings
        return out

    def get(self, aoi_id: UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(text(f"SELECT {_FULL} FROM aoi WHERE id=:i"), {"i": aoi_id}).first()
        return None if row is None else _row(row._mapping)

    def list(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            total = conn.execute(text("SELECT count(*) FROM aoi")).scalar_one()
            rows = conn.execute(
                text(
                    "SELECT id, name, source AS method, "
                    "ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] AS bbox, "
                    "area_km2, created_at FROM aoi ORDER BY created_at DESC, id LIMIT :l OFFSET :o"
                ),
                {"l": limit, "o": offset},
            ).all()
        return [dict(r._mapping) for r in rows], total

    def delete(self, aoi_id: UUID) -> bool:
        with self._engine.begin() as conn:
            return (
                conn.execute(text("DELETE FROM aoi WHERE id=:i RETURNING id"), {"i": aoi_id}).first()
                is not None
            )
