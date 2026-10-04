# Phase 2 Plan — AOI Input and Map Basics

Status: **approved to start 2026-10-04** (owner: keep narrow and reviewable). Governing: ADR-0005, ADR-0008, ADR-0012.

## Scope
In: AOI input UX, 2D map basics, point+radius, rectangle/polygon drawing, AOI validation, upload (GeoJSON/KML/KMZ/zipped Shapefile), AOI endpoints and persistence, AOI list/reload.
Out (not started, must not appear): Earth Engine, thermal/gold/void scoring, remote-sensing analysis, 3D rendering, any scientific inference layer, any result display. AOI responses contain geometry and bookkeeping only.

## Tasks
| ID | Task | Done when |
|---|---|---|
| P2-01 | Docs: closeout, job lifecycle, ADR-0012, this plan | merged |
| P2-02 | Config + migration 0002 (`aoi` columns, `MAX_STORED_AOIS`) | up/down/up test passes |
| P2-03 | Geometry core: circle, rectangle, polygon, normalisation, validation, geodesic area, UTM zone | reference-value and boundary tests (area 25 km², radius 2.5 km, min 0.01 km², vertices, lat/lon ranges, antimeridian, poles, self-intersection) |
| P2-04 | Upload parsers + hardening (GeoJSON, KML, KMZ, zipped Shapefile) | hostile-input tests: zip bomb, traversal names, encrypted, nested, bad CRS, no `.prj`, multi-feature, XXE/entity expansion, oversize |
| P2-05 | AOI repository + API: preview, create, upload, list, get, delete, limits | integration tests incl. 409 at `MAX_STORED_AOIS`, 404, 422 bodies |
| P2-06 | Contracts: AOI schemas → Pydantic + TS | `make schemas-check` clean |
| P2-07 | Frontend: MapLibre map, point/radius, rectangle, polygon, upload, numeric forms, AOI list, reload | unit tests + headless browser check |
| P2-08 | Guards/CI/licences/docs updated; acceptance evidence in `docs/phase-reports/phase-2.md` | `make ci` green locally and on GitHub Actions |

## Explicit non-goals
Projects/grouping entity, vertex editing, multi-part AOIs, antimeridian/polar AOIs, automatic tiling of large AOIs, authentication, any connector.
