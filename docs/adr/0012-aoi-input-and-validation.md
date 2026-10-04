# ADR-0012: AOI input, validation and basemap handling (Phase 2)

- **Status:** Accepted within the Phase 2 scope approved by the owner (2026-10-04); owner may veto any point
- **Date:** 2026-10-04
- **Decided by:** Claude (design), under the owner's Phase 2 approval

## Context
Phase 2 adds AOI input (point+radius, rectangle, polygon, GeoJSON/KML/KMZ/zipped Shapefile upload), validation, persistence and a 2D map. AOIs are user data and may be sensitive (ADR-0005, CLAUDE.md §8). This ADR contains **no analysis or scientific inference**: an AOI is only a validated geometry plus bookkeeping.

## Decision
1. **Stored geometry:** exactly one `Polygon` (interior rings allowed) in EPSG:4326. A `MultiPolygon` with a single part is accepted; multi-part inputs and every other geometry type are rejected (the user uploads parts separately).
2. **No silent repair:** invalid geometry (self-intersection, <3 distinct vertices, non-finite coordinates) is rejected with the reason; `make_valid`/buffer(0) are never applied. Only trivial normalisation: closing an open ring, dropping consecutive duplicate points, dropping Z/M, consistent ring orientation.
3. **Unsupported regions, rejected explicitly:** AOIs crossing the antimeridian, and any vertex with |latitude| > 85° (working CRS is UTM; polar projections are out of scope).
4. **Area:** geodesic on the WGS84 ellipsoid (`pyproj.Geod`); the polygon's area is what is limited and reported, not π·r². Limits per ADR-0008 (provisional operational safeguards, enforced server-side).
5. **Point + radius:** geodesic circle approximated by 72 vertices (5° step); `radius_m` ∈ (0, `MAX_RADIUS_KM`·1000]; the stored `details` record centre and radius.
6. **Working CRS:** UTM zone chosen from the centroid (EPSG:326xx north / 327xx south) and stored for later phases; it is not used for any computation in Phase 2.
7. **Upload formats and parsers** (no GDAL/Fiona): GeoJSON (stdlib `json`; WGS84 only, legacy `crs` member rejected unless CRS84/4326); KML (`defusedxml`, DTD/entities forbidden); KMZ (`zipfile`, reads `doc.kml` or the single `.kml`); zipped Shapefile (`pyshp`, **`.prj` required**, reprojected to 4326 with `pyproj`). Exactly one polygon feature per file.
8. **Archive hardening:** nothing is extracted to disk; members are read into memory with a byte cap; reject encrypted entries, absolute/`..` names, nested archives, more than `MAX_ARCHIVE_FILES` entries, or more than `MAX_ARCHIVE_UNCOMPRESSED_MB` actually-read bytes (declared sizes are not trusted); reject upload larger than `MAX_UPLOAD_MB`; file type decided by extension **and** content sniffing.
9. **Persistence cap:** `MAX_STORED_AOIS` (default 100, new env var) bounds storage; creation beyond it returns 409.
10. **Map:** MapLibre GL JS (BSD-3-Clause). Drawing (rectangle, polygon, centre click) is implemented with plain map events, no draw plugin. Vertex editing is deferred; redraw instead. Numeric forms are the keyboard-accessible alternative.
11. **Basemap privacy:** *(superseded by ADR-0013 amendment: the default is now `none`; OpenStreetMap is opt-in for local development only.)* Originally: the default basemap was OpenStreetMap raster tiles, configurable by `NEXT_PUBLIC_BASEMAP_TILE_URL` (empty value = no basemap). **Tile requests disclose the viewed map area to the tile provider** (AOI geometry itself is never sent). OSM's tile policy discourages heavy use; this default is for low-volume development only (policy not re-verified here).
12. **No Project entity yet.** The "project scaffolding" the owner mentioned is satisfied by a named, persisted AOI. A grouping `project` table is deferred until a phase needs it (backlog).

## Consequences
- New runtime dependencies: `shapely` (BSD-3), `pyproj` (MIT), `pyshp` (MIT), `defusedxml` (PSF), `python-multipart` (Apache-2.0), `maplibre-gl` (BSD-3) — recorded in the licence register.
- Users with AOIs over 25 km², antimeridian or polar AOIs, or multi-part files must adapt their input (documented in API errors).
- Geodesic circle/area math is validated against reference values in tests.

## Revisit when
Projects/grouping, vertex editing, multi-part AOIs, or polar/antimeridian support are requested.
