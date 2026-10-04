"""Upload parsers: GeoJSON, KML, KMZ, zipped Shapefile -> RawPolygon (ADR-0012 §7)."""

from __future__ import annotations

import io
import json
import math
import re
from collections.abc import Sequence
from typing import Any
from xml.etree.ElementTree import Element, ParseError  # noqa: S405 - types only; parsing is via defusedxml

import defusedxml.ElementTree as SafeET
import shapefile
from defusedxml import DefusedXmlException
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError

from app.aoi.archive import open_safe_zip
from app.aoi.errors import AoiValidationError
from app.aoi.geometry import RawPolygon

SUPPORTED_FORMATS = ["geojson", "kml", "kmz", "shapefile"]
_WGS84_NAMES = {
    "urn:ogc:def:crs:ogc:1.3:crs84",
    "urn:ogc:def:crs:epsg::4326",
    "epsg:4326",
    "crs84",
    "urn:ogc:def:crs:epsg:6.6:4326",
}
POLYGON_SHAPE_TYPES = {5, 15, 25}  # POLYGON, POLYGONZ, POLYGONM


def safe_filename(name: str | None) -> str:
    base = re.split(r"[\\/]", name or "upload")[-1]
    base = re.sub(r"[^\w.\- ]", "_", base)[:100].strip()
    return base or "upload"


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ring(coords: Any, what: str) -> list[Sequence[float]]:
    if not isinstance(coords, (list, tuple)) or not all(
        isinstance(p, (list, tuple)) and len(p) >= 2 and _num(p[0]) and _num(p[1]) for p in coords
    ):
        raise AoiValidationError("invalid_coordinate", f"{what}: coordinates must be [lon, lat] number pairs")
    return [list(p[:2]) for p in coords]


def _polygon_from_geometry(geom: Any) -> RawPolygon:
    if not isinstance(geom, dict):
        raise AoiValidationError("unsupported_geometry", "geometry must be an object")
    gtype, coords = geom.get("type"), geom.get("coordinates")
    if gtype == "MultiPolygon":
        if not isinstance(coords, (list, tuple)) or len(coords) != 1:
            raise AoiValidationError(
                "multipart_unsupported", "only a single polygon is supported; upload parts separately"
            )
        coords, gtype = coords[0], "Polygon"
    if gtype != "Polygon":
        raise AoiValidationError(
            "unsupported_geometry", f"geometry type '{gtype}' is not supported; a single Polygon is required"
        )
    if not isinstance(coords, (list, tuple)) or not coords:
        raise AoiValidationError("invalid_coordinate", "polygon has no rings")
    return RawPolygon(
        _ring(coords[0], "outer ring"), [_ring(h, f"hole {i + 1}") for i, h in enumerate(coords[1:])]
    )


# --------------------------------------------------------------------------- GeoJSON
def parse_geojson(data: bytes) -> tuple[RawPolygon, dict[str, Any]]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise AoiValidationError(
            "invalid_geojson", "file is not valid GeoJSON (UTF-8 JSON expected)"
        ) from exc
    if not isinstance(doc, dict):
        raise AoiValidationError("invalid_geojson", "GeoJSON root must be an object")
    crs = doc.get("crs")
    if crs is not None:
        name = ((crs.get("properties") or {}).get("name") if isinstance(crs, dict) else None) or ""
        if str(name).lower() not in _WGS84_NAMES:
            raise AoiValidationError(
                "unsupported_crs", f"GeoJSON crs '{name}' is not supported; use WGS84 (EPSG:4326)"
            )
    t = doc.get("type")
    if t == "FeatureCollection":
        feats = doc.get("features")
        if not isinstance(feats, list) or len(feats) != 1:
            raise AoiValidationError(
                "not_single_feature", "FeatureCollection must contain exactly one feature"
            )
        geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
    elif t == "Feature":
        geom = doc.get("geometry")
    else:
        geom = doc
    return _polygon_from_geometry(geom), {"format": "geojson"}


# --------------------------------------------------------------------------- KML
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_coords(text: str | None, what: str) -> list[Sequence[float]]:
    pts: list[Sequence[float]] = []
    for tok in (text or "").split():
        parts = tok.split(",")
        try:
            vals = [float(x) for x in parts[:2]]
        except ValueError as exc:
            raise AoiValidationError(
                "invalid_coordinate", f"{what}: bad KML coordinate '{tok[:30]}'"
            ) from exc
        if len(parts) < 2:
            raise AoiValidationError("invalid_coordinate", f"{what}: KML coordinate needs lon,lat")
        pts.append(vals)
    return pts


def _find(el: Element, name: str) -> list[Element]:
    return [e for e in el.iter() if _local(e.tag) == name]


def parse_kml(data: bytes) -> tuple[RawPolygon, dict[str, Any]]:
    try:
        root = SafeET.fromstring(data, forbid_dtd=True)
    except DefusedXmlException as exc:
        raise AoiValidationError("xml_forbidden", "XML with DTDs/entities is not accepted") from exc
    except (ParseError, ValueError) as exc:
        raise AoiValidationError("invalid_kml", "file is not valid KML/XML") from exc
    polygons = _find(root, "Polygon")
    if not polygons:
        raise AoiValidationError("no_polygon", "no Polygon found in KML (points/lines are not AOIs)")
    if len(polygons) > 1:
        raise AoiValidationError("multipart_unsupported", "KML must contain exactly one Polygon")
    poly = polygons[0]
    outer = [c for b in _find(poly, "outerBoundaryIs") for c in _find(b, "coordinates")]
    if len(outer) != 1:
        raise AoiValidationError("invalid_kml", "Polygon needs exactly one outerBoundaryIs with coordinates")
    holes = [
        _kml_coords(c.text, f"hole {i + 1}")
        for i, c in enumerate(c for b in _find(poly, "innerBoundaryIs") for c in _find(b, "coordinates"))
    ]
    return RawPolygon(_kml_coords(outer[0].text, "outer ring"), holes), {"format": "kml"}


def parse_kmz(data: bytes, max_files: int, max_mb: int) -> tuple[RawPolygon, dict[str, Any]]:
    sz = open_safe_zip(data, max_files, max_mb)
    kmls = [n for n in sz.names() if n.lower().endswith(".kml")]
    chosen = next((n for n in kmls if n.lower() in ("doc.kml",)), None) or (
        kmls[0] if len(kmls) == 1 else None
    )
    if chosen is None:
        raise AoiValidationError("invalid_kmz", "KMZ must contain doc.kml or exactly one .kml file")
    raw, _ = parse_kml(sz.read(chosen))
    return raw, {"format": "kmz"}


# --------------------------------------------------------------------------- Shapefile
def _transform_coords(coords: Any, tr: Transformer) -> Any:
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        x, y = tr.transform(coords[0], coords[1])
        return [x, y]
    return [_transform_coords(c, tr) for c in coords]


def parse_shapefile_zip(data: bytes, max_files: int, max_mb: int) -> tuple[RawPolygon, dict[str, Any]]:
    sz = open_safe_zip(data, max_files, max_mb)
    by_ext: dict[str, list[str]] = {}
    for n in sz.names():
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
        by_ext.setdefault(ext, []).append(n)
    shps = by_ext.get("shp", [])
    if len(shps) != 1:
        raise AoiValidationError("invalid_shapefile", "zip must contain exactly one .shp file")
    stem = shps[0][: -len(".shp")]
    prj_names = [n for n in by_ext.get("prj", []) if n[: -len(".prj")].lower() == stem.lower()]
    if not prj_names:
        raise AoiValidationError("missing_prj", "Shapefile .prj (coordinate system) is required")
    try:
        crs = CRS.from_wkt(sz.read(prj_names[0]).decode("utf-8", errors="replace"))
    except CRSError as exc:
        raise AoiValidationError("unsupported_crs", "Shapefile .prj could not be interpreted") from exc
    shp = sz.read(shps[0])
    shx_names = [n for n in by_ext.get("shx", []) if n[: -len(".shx")].lower() == stem.lower()]
    dbf_names = [n for n in by_ext.get("dbf", []) if n[: -len(".dbf")].lower() == stem.lower()]
    try:
        reader = shapefile.Reader(
            shp=io.BytesIO(shp),
            shx=io.BytesIO(sz.read(shx_names[0])) if shx_names else None,
            dbf=io.BytesIO(sz.read(dbf_names[0])) if dbf_names else None,
        )
        shapes = reader.shapes()
        shape_type = reader.shapeType
    except Exception as exc:  # pyshp raises assorted errors on malformed input
        raise AoiValidationError("invalid_shapefile", "Shapefile could not be read") from exc
    if shape_type not in POLYGON_SHAPE_TYPES:
        raise AoiValidationError("unsupported_geometry", "Shapefile must contain polygons")
    if len(shapes) != 1:
        raise AoiValidationError(
            "not_single_feature", f"Shapefile has {len(shapes)} features; exactly one required"
        )
    geom = shapes[0].__geo_interface__
    source_crs = crs.to_string()
    if not crs.equals(CRS.from_epsg(4326)) and not crs.equals(CRS.from_user_input("OGC:CRS84")):
        try:
            tr = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
            geom = {"type": geom["type"], "coordinates": _transform_coords(geom["coordinates"], tr)}
        except Exception as exc:
            raise AoiValidationError("unsupported_crs", "could not reproject Shapefile to EPSG:4326") from exc
    return _polygon_from_geometry(geom), {"format": "shapefile", "source_crs": source_crs}


# --------------------------------------------------------------------------- dispatcher
def parse_upload(
    filename: str, data: bytes, max_files: int, max_mb: int
) -> tuple[RawPolygon, str, dict[str, Any]]:
    """Return (raw polygon, method, details). Type is decided by extension AND content."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    head = data[:512].lstrip(b"\xef\xbb\xbf \t\r\n")
    is_zip = data[:4] == b"PK\x03\x04"
    if ext in ("geojson", "json"):
        if not head.startswith(b"{"):
            raise AoiValidationError("file_type_mismatch", "file content does not look like GeoJSON")
        raw, d = parse_geojson(data)
        method = "geojson"
    elif ext == "kml":
        if not head.startswith(b"<"):
            raise AoiValidationError("file_type_mismatch", "file content does not look like KML")
        raw, d = parse_kml(data)
        method = "kml"
    elif ext == "kmz":
        if not is_zip:
            raise AoiValidationError("file_type_mismatch", "file content is not a ZIP/KMZ archive")
        raw, d = parse_kmz(data, max_files, max_mb)
        method = "kmz"
    elif ext == "zip":
        if not is_zip:
            raise AoiValidationError("file_type_mismatch", "file content is not a ZIP archive")
        raw, d = parse_shapefile_zip(data, max_files, max_mb)
        method = "shapefile"
    else:
        raise AoiValidationError(
            "unsupported_file_type", "supported uploads: .geojson/.json, .kml, .kmz, .zip (Shapefile)"
        )
    return raw, method, {**d, "filename": safe_filename(filename)}
