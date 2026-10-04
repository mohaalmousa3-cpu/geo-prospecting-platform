"""AOI geometry construction and validation (ADR-0012). No silent repair of invalid input."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import shapely
from pyproj import Geod
from shapely.geometry import Polygon, mapping
from shapely.geometry.polygon import orient
from shapely.validation import explain_validity

from app.aoi.errors import AoiValidationError
from geo_common.config import Settings

GEOD = Geod(ellps="WGS84")
CIRCLE_VERTICES = 72  # 5 degree step
MAX_ABS_LATITUDE = 85.0
ANTIMERIDIAN_JUMP_DEG = 180.0

Coord = tuple[float, float]


@dataclass(frozen=True)
class AoiLimitsConfig:
    max_area_km2: float
    min_area_km2: float
    max_radius_m: float
    max_vertices: int

    @classmethod
    def from_settings(cls, s: Settings) -> AoiLimitsConfig:
        return cls(s.MAX_AOI_AREA_KM2, s.MIN_AOI_AREA_KM2, s.MAX_RADIUS_KM * 1000.0, s.MAX_AOI_VERTICES)


@dataclass(frozen=True)
class RawPolygon:
    """Parser output: rings of (lon, lat) in EPSG:4326, not yet validated."""

    shell: list[Sequence[float]]
    holes: list[list[Sequence[float]]] = field(default_factory=list)


@dataclass(frozen=True)
class AoiGeometry:
    polygon: Polygon
    area_km2: float
    vertex_count: int
    working_crs: str
    bbox: tuple[float, float, float, float]
    warnings: list[str]

    def geojson(self) -> dict[str, object]:
        return dict(mapping(self.polygon))


def utm_epsg(lon: float, lat: float) -> str:
    zone = min(60, max(1, int((lon + 180.0) // 6.0) + 1))
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def _clean_ring(ring: Sequence[Sequence[float]], what: str, warnings: list[str]) -> list[Coord]:
    pts: list[Coord] = []
    dropped = 0
    was_closed = len(ring) >= 2 and tuple(ring[0][:2]) == tuple(ring[-1][:2])
    for p in ring:
        if len(p) < 2:
            raise AoiValidationError("invalid_coordinate", f"{what}: coordinate needs lon and lat")
        lon, lat = p[0], p[1]
        if isinstance(lon, bool) or isinstance(lat, bool):
            raise AoiValidationError("invalid_coordinate", f"{what}: coordinates must be numbers")
        lon, lat = float(lon), float(lat)
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise AoiValidationError("invalid_coordinate", f"{what}: non-finite coordinate")
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise AoiValidationError(
                "coordinate_out_of_range",
                f"{what}: lon/lat out of range (lon {lon}, lat {lat}); expected lon -180..180, lat -90..90",
            )
        if abs(lat) > MAX_ABS_LATITUDE:
            raise AoiValidationError(
                "latitude_unsupported",
                f"{what}: |latitude| > {MAX_ABS_LATITUDE:g} is not supported in V1 (lat {lat})",
            )
        if pts and pts[-1] == (lon, lat):
            dropped += 1
            continue
        pts.append((lon, lat))
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()  # closing duplicate; re-added below
    if not was_closed:
        warnings.append(f"{what}: ring was not closed; closed automatically")
    if dropped:
        warnings.append(f"{what}: removed {dropped} consecutive duplicate point(s)")
    if len(pts) < 3:
        raise AoiValidationError("too_few_vertices", f"{what}: needs at least 3 distinct vertices")
    ring_closed = [*pts, pts[0]]
    for a, b in zip(ring_closed, ring_closed[1:], strict=False):
        if abs(a[0] - b[0]) > ANTIMERIDIAN_JUMP_DEG:
            raise AoiValidationError(
                "antimeridian_unsupported", f"{what}: crossing the antimeridian is not supported in V1"
            )
    return ring_closed


def build_polygon(raw: RawPolygon, limits: AoiLimitsConfig) -> AoiGeometry:
    warnings: list[str] = []
    shell = _clean_ring(raw.shell, "outer ring", warnings)
    holes = [_clean_ring(h, f"hole {i + 1}", warnings) for i, h in enumerate(raw.holes)]
    vertex_count = (len(shell) - 1) + sum(len(h) - 1 for h in holes)
    if vertex_count > limits.max_vertices:
        raise AoiValidationError(
            "too_many_vertices",
            f"AOI has {vertex_count} vertices, exceeding MAX_AOI_VERTICES={limits.max_vertices}",
        )
    poly = Polygon(shell, holes)
    if not shapely.is_valid(poly):
        raise AoiValidationError("invalid_geometry", f"invalid polygon: {explain_validity(poly)}")
    poly = orient(poly)
    area_km2 = abs(GEOD.geometry_area_perimeter(poly)[0]) / 1e6
    if area_km2 < limits.min_area_km2:
        raise AoiValidationError(
            "area_too_small",
            f"AOI area {area_km2:.4f} km2 is below MIN_AOI_AREA_KM2={limits.min_area_km2:g}",
        )
    if area_km2 > limits.max_area_km2:
        raise AoiValidationError(
            "area_too_large",
            f"AOI area {area_km2:.2f} km2 exceeds MAX_AOI_AREA_KM2={limits.max_area_km2:g}",
        )
    c = poly.centroid
    minx, miny, maxx, maxy = poly.bounds
    return AoiGeometry(poly, area_km2, vertex_count, utm_epsg(c.x, c.y), (minx, miny, maxx, maxy), warnings)


def circle_ring(lat: float, lon: float, radius_m: float, limits: AoiLimitsConfig) -> list[Coord]:
    if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(radius_m)):
        raise AoiValidationError("invalid_coordinate", "centre and radius must be finite numbers")
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise AoiValidationError("coordinate_out_of_range", f"centre out of range (lat {lat}, lon {lon})")
    if abs(lat) > MAX_ABS_LATITUDE:
        raise AoiValidationError(
            "latitude_unsupported", f"|latitude| > {MAX_ABS_LATITUDE:g} is not supported in V1"
        )
    if radius_m <= 0:
        raise AoiValidationError("invalid_radius", "radius must be greater than 0")
    if radius_m > limits.max_radius_m:
        raise AoiValidationError(
            "radius_too_large",
            f"radius {radius_m:g} m exceeds MAX_RADIUS_KM={limits.max_radius_m / 1000:g}",
        )
    azimuths = [i * 360.0 / CIRCLE_VERTICES for i in range(CIRCLE_VERTICES)]
    lons, lats, _ = GEOD.fwd(
        [lon] * CIRCLE_VERTICES, [lat] * CIRCLE_VERTICES, azimuths, [radius_m] * CIRCLE_VERTICES
    )
    return list(zip(lons, lats, strict=True))


def rectangle_ring(west: float, south: float, east: float, north: float) -> list[Coord]:
    if not all(math.isfinite(v) for v in (west, south, east, north)):
        raise AoiValidationError("invalid_coordinate", "rectangle bounds must be finite numbers")
    if west >= east or south >= north:
        raise AoiValidationError(
            "invalid_rectangle",
            "rectangle needs west < east and south < north (antimeridian-crossing is unsupported)",
        )
    return [(west, south), (east, south), (east, north), (west, north)]
