# TASKS.md — Phased Implementation Roadmap

Legend: `[ ]` todo · `[x]` done and verified · Only the **current phase** may be worked on (see `CLAUDE.md`).
Acceptance criteria per phase: `docs/acceptance-criteria.md`.

**Current phase: 0 (completing)**

---

## Phase 0 — Planning and Scaffolding
- [x] Repository structure and placeholder READMEs
- [x] MASTER_SPEC.md, CLAUDE.md, TASKS.md, README.md
- [x] docs: architecture, scientific-constraints, dependency-strategy, data-sources, acceptance-criteria, risk-register
- [x] .env.example, .gitignore, LICENSE guidance
- [ ] User review and resolution of Open Questions (see end of this file)
- [ ] User sign-off to start Phase 1

## Phase 1 — Repo/App Foundation
- [ ] Decide licence (ADR-0001) and add LICENSE
- [ ] Decide queue library (ADR-0002) and object storage default (ADR-0003)
- [ ] Docker Compose: postgres+postgis, redis, backend, worker, frontend
- [ ] FastAPI skeleton: `/health`, config loading, structured logging, versioned API prefix
- [ ] DB migrations setup (Alembic) with PostGIS enabled; initial tables: `aoi`, `job`, `result`, `provenance`
- [ ] Worker skeleton: consumes a no-op job, records status transitions
- [ ] Next.js skeleton (TypeScript, lint, formatting) with a status page calling `/health`
- [ ] Shared schema pipeline: JSON Schema → Pydantic + TS types
- [ ] Mandatory result envelope schema (confidence, uncertainty, evidence, sources, disclaimer)
- [ ] CI: lint, type-check, unit tests, schema validation, secret scan
- [ ] Pre-commit hooks; contribution notes
- [ ] Scientific-guard test scaffold (forbidden-term check, envelope completeness)

## Phase 2 — AOI Input and Map Basics
- [ ] AOI model + API: create/get/list/delete
- [ ] Coordinates + radius → polygon (geodesically correct)
- [ ] Geometry validation, CRS normalisation, area limits, simplification
- [ ] Upload parsers: GeoJSON, KML, KMZ, zipped Shapefile (with hardened extraction)
- [ ] MapLibre 2D map: base map, draw rectangle/polygon, edit, display uploaded AOI
- [ ] Coordinate/radius input form
- [ ] AOI persistence and reload
- [ ] Tests: malformed/hostile uploads, antimeridian, self-intersections, huge AOIs

## Phase 3 — Remote Sensing Connectors
- [ ] Connector interface (inputs, outputs, quotas, caching, provenance)
- [ ] STAC connector (open catalogues) — Landsat, Sentinel-2, Sentinel-1 metadata/assets
- [ ] DEM connector (open DEM, e.g. Copernicus/SRTM — final choice via ADR)
- [ ] Geology / mineral-occurrence connector(s) (open datasets only)
- [ ] Google Earth Engine connector — **optional**, behind feature flag, requires user approval + credentials
- [ ] Caching layer, request budgets, retry/back-off, offline mock fixtures
- [ ] Provenance capture for every fetched asset
- [ ] Tests with recorded fixtures (no live calls in CI)

## Phase 4 — Thermal Pipeline
- [ ] Engine design doc (`workers/thermal/README.md`): method, assumptions, limits
- [ ] Landsat LST retrieval from Collection 2 surface temperature products
- [ ] Cloud/quality masking; scene selection; seasonal/diurnal handling
- [ ] Anomaly detection (documented statistical method, uncertainty propagated)
- [ ] Temporal stability / persistence assessment
- [ ] Output: `thermal_anomaly` raster + uncertainty raster + provenance
- [ ] Validation notes and known-failure documentation (topography, albedo, moisture, emissivity)

## Phase 5 — Gold Prospectivity Pipeline
- [ ] Engine design doc: evidence layers, method (knowledge-driven / data-driven), limits
- [ ] Evidence layer builders (alteration indices, lineaments, lithology proximity, geochemistry if available)
- [ ] Integration via EIS Toolkit (or alternative per ADR)
- [ ] Prospectivity surface + uncertainty surface
- [ ] Target extraction, ranking, explanation generation
- [ ] Validation against known deposits where data exist; document spatial-CV method
- [ ] Mark engine *experimental* until validation criteria met

## Phase 6 — Void Evidence Pipeline
- [ ] Engine design doc: what each evidence type can and cannot indicate
- [ ] Evidence layers: terrain (sinks, depressions, karst/lithology context), thermal, optional InSAR deformation, geology
- [ ] Multi-evidence integration → `void_evidence_score` (never "cave detected")
- [ ] Target extraction, ranking, explanation, counter-evidence listing
- [ ] Optional MintPy worker (separate image, off by default)
- [ ] Safety messaging: no entry/excavation guidance
- [ ] Validation notes against documented sites where available

## Phase 7 — 3D Visualization
- [ ] CesiumJS viewer integrated in Next.js
- [ ] Terrain source selection (open) and token-free default
- [ ] Drape raster layers and targets; uncertainty display
- [ ] Target selection ↔ explanation panel
- [ ] Performance budget & level-of-detail strategy
- [ ] Verify no depth is rendered without geophysics provenance

## Phase 8 — Field Geophysics Ingestion
- [ ] ADR: supported file formats per method (ERT, IP, GPR, magnetics)
- [ ] Upload, validation, storage, metadata capture (survey geometry, instrument, CRS)
- [ ] ERT/IP processing & inversion via ResIPy/pyGIMLi wrappers
- [ ] GPR processing via GPRPy wrapper
- [ ] Magnetic data gridding / basic processing (method per ADR)
- [ ] Display sections/volumes; inversion uncertainty & non-uniqueness warnings
- [ ] Link geophysics results to targets; depth shown only with geophysics provenance
- [ ] Optional GemPy modelling (separate image, off by default)

## Phase 9 — Confidence, Uncertainty and Reporting Refinement
- [ ] Unified confidence/uncertainty methodology doc and implementation across engines
- [ ] Calibration checks where validation data exist; otherwise label as uncalibrated
- [ ] Explanation quality review (evidence + counter-evidence + limitations)
- [ ] Report generator (HTML/PDF) + GeoJSON/GeoPackage export
- [ ] Language audit across UI/API/reports against scientific constraints
- [ ] Performance, scaling and cost review; documented limits
- [ ] Security review (uploads, auth, data handling)

---

## Backlog (unscheduled; do not implement without approval)
- Authentication / multi-user / projects
- Hyperspectral (EnMAP/PRISMA) ingestion
- Time-series change detection
- Mobile/offline field companion
- Collaborative annotation

## Open Questions (require user approval)
1. **Licence** for this repository (affects use of GPL/EUPL dependencies).
2. **Queue library** (Celery / Dramatiq / RQ / arq).
3. **Object storage** default (local volume vs MinIO).
4. **Earth Engine**: allowed at all? Whose credentials/quota? (non-commercial vs commercial terms)
5. **Target regions / deposit types** — gold models are deposit-type specific; which type(s) first?
6. **Validation data** — are there known sites/benchmarks the user can provide?
7. **Authentication** needs in the first release.
8. **Compute budget** — target hardware and per-job limits.
9. **Hosting target** for eventual deployment.
