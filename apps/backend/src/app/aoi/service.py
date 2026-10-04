"""Turn validated requests/uploads into a normalised AoiDraft (no persistence, no analysis)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.aoi.geometry import (
    AoiGeometry,
    AoiLimitsConfig,
    RawPolygon,
    build_polygon,
    circle_ring,
    rectangle_ring,
)
from app.aoi.parsers import SUPPORTED_FORMATS, parse_upload, safe_filename
from geo_common.config import Settings
from geo_common.models._generated import (
    AoiLimits,
    AoiPointRadiusRequest,
    AoiPolygonRequest,
    AoiRectangleRequest,
)

AoiRequest = AoiPointRadiusRequest | AoiRectangleRequest | AoiPolygonRequest


class Draft:
    def __init__(self, method: str, geom: AoiGeometry, details: dict[str, Any], name: str | None) -> None:
        self.method, self.geom, self.details, self.name = method, geom, details, name

    def as_dict(self) -> dict[str, Any]:
        g = self.geom
        return {
            "method": self.method,
            "geometry": g.geojson(),
            "bbox": list(g.bbox),
            "area_km2": g.area_km2,
            "vertex_count": g.vertex_count,
            "working_crs": g.working_crs,
            "details": self.details,
            "warnings": g.warnings,
        }


def limits_view(s: Settings) -> AoiLimits:
    return AoiLimits(
        max_area_km2=s.MAX_AOI_AREA_KM2,
        min_area_km2=s.MIN_AOI_AREA_KM2,
        max_radius_m=s.MAX_RADIUS_KM * 1000.0,
        max_vertices=s.MAX_AOI_VERTICES,
        max_upload_mb=s.MAX_UPLOAD_MB,
        max_stored_aois=s.MAX_STORED_AOIS,
        max_abs_latitude=85.0,
        supported_upload_formats=SUPPORTED_FORMATS,
    )


def draft_from_request(req: AoiRequest, s: Settings) -> Draft:
    limits = AoiLimitsConfig.from_settings(s)
    name = req.name.root if req.name is not None else None
    if isinstance(req, AoiPointRadiusRequest):
        ring = circle_ring(req.lat, req.lon, req.radius_m, limits)
        details = {"lat": req.lat, "lon": req.lon, "radius_m": req.radius_m, "circle_vertices": len(ring)}
        return Draft("point_radius", build_polygon(RawPolygon(list(ring)), limits), details, name)
    if isinstance(req, AoiRectangleRequest):
        ring = rectangle_ring(req.west, req.south, req.east, req.north)
        details = {"west": req.west, "south": req.south, "east": req.east, "north": req.north}
        return Draft("rectangle", build_polygon(RawPolygon(list(ring)), limits), details, name)
    shell: list[Sequence[float]] = [list(p.root) for p in req.coordinates]
    return Draft("polygon", build_polygon(RawPolygon(shell), limits), {}, name)


def draft_from_upload(filename: str, data: bytes, s: Settings, name: str | None) -> Draft:
    limits = AoiLimitsConfig.from_settings(s)
    raw, method, details = parse_upload(filename, data, s.MAX_ARCHIVE_FILES, s.MAX_ARCHIVE_UNCOMPRESSED_MB)
    stem = safe_filename(filename).rsplit(".", 1)[0]
    return Draft(method, build_polygon(raw, limits), details, name or stem[:120] or "uploaded AOI")
