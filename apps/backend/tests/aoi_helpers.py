from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import shapefile
from pyproj import Geod

from app.aoi.geometry import AoiLimitsConfig

GEOD = Geod(ellps="WGS84")
LIMITS = AoiLimitsConfig(max_area_km2=25, min_area_km2=0.01, max_radius_m=2500, max_vertices=2000)


def ring_area_km2(ring: list[list[float]]) -> float:
    lons, lats = zip(*ring, strict=True)
    return abs(GEOD.polygon_area_perimeter(lons, lats)[0]) / 1e6


def square_with_area(km2: float, lon: float = 10.0, lat: float = 0.0) -> list[list[float]]:
    """Closed square ring (degrees) whose geodesic area is km2 (bisection on the side length)."""
    lo, hi = 1e-6, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        ring = [[lon, lat], [lon + mid, lat], [lon + mid, lat + mid], [lon, lat + mid], [lon, lat]]
        if ring_area_km2(ring) < km2:
            lo = mid
        else:
            hi = mid
    return ring


def geojson_polygon(ring: list[list[float]]) -> bytes:
    return json.dumps({"type": "Polygon", "coordinates": [ring]}).encode()


def kml(ring: list[list[float]], extra: str = "") -> bytes:
    coords = " ".join(f"{x},{y},0" for x, y in ring)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>t</name>'
        f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing>"
        f"</outerBoundaryIs></Polygon>{extra}</Placemark></Document></kml>"
    ).encode()


def make_zip(files: dict[str, bytes], compress: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compress) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def shapefile_zip(rings: list[list[list[float]]], prj: str | None = WGS84_PRJ, features: int = 1) -> bytes:
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON) as w:
        w.field("NAME", "C")
        for i in range(features):
            w.poly(rings)
            w.record(f"f{i}")
    files: dict[str, bytes] = {
        "aoi.shp": shp.getvalue(),
        "aoi.shx": shx.getvalue(),
        "aoi.dbf": dbf.getvalue(),
    }
    if prj is not None:
        files["aoi.prj"] = prj.encode()
    return make_zip(files)


def cw(ring: list[list[float]]) -> list[list[float]]:
    """Shapefile outer rings are clockwise."""
    return list(reversed(ring))


def feature(geometry: dict[str, Any]) -> bytes:
    return json.dumps({"type": "Feature", "properties": {}, "geometry": geometry}).encode()
