# TASKS.md — Phased Implementation Roadmap

Legend: `[ ]` todo · `[x]` done and verified · Only the **current phase** may be worked on (see `CLAUDE.md`).
Acceptance criteria per phase: `docs/acceptance-criteria.md`.

**Current phase: 2 — implemented, awaiting owner acceptance (`docs/phase-reports/phase-2.md`). Phase 1 accepted with follow-ups (`docs/phase-reports/phase-1-closeout.md`).** Owner decisions are recorded as ADRs (`docs/adr/`, 0001…0012). Not started and not allowed yet: Earth Engine, thermal/gold/void scoring, remote-sensing analysis, 3D rendering, any scientific inference layer.

---

## Phase 0 — Planning and Scaffolding
- [x] Repository structure and placeholder READMEs
- [x] MASTER_SPEC.md, CLAUDE.md, TASKS.md, README.md
- [x] docs: architecture, scientific-constraints, dependency-strategy, data-sources, acceptance-criteria, risk-register
- [x] .env.example, .gitignore, LICENSE guidance
- [x] Owner decisions recorded as ADRs 0001–0010 and docs updated accordingly
- [x] Phase 1 plan drafted (`docs/phase-1-plan.md`)
- [x] Owner approval of Phase 1 plan and technical choices; T8 recorded as ADR-0011
- [x] Owner confirmation of field-validation definitions (ADR-0010, stricter wording)

## Phase 1 — Repo/App Foundation
Implemented 2026-10-04; evidence and deviations in `docs/phase-reports/phase-1.md`. **Awaiting owner acceptance** before Phase 2. Detailed, ordered tasks with verification commands: **`docs/phase-1-plan.md`** (P1-01 … P1-18). Summary:
- [x] Tooling baseline (lint, type-check, tests, secret scan, forbidden-term scan)
- [ ] CI workflow executed green on GitHub Actions (written; passes locally via `make ci`)
- [x] Docker Compose: postgis, backend, worker, frontend — loopback ports, no Redis, no MinIO
- [x] FastAPI skeleton: `/health`, config, logging, `/api/v1`
- [x] Alembic + PostGIS; tables `aoi`, `job`, `result`, `provenance`
- [x] `StorageBackend` (local) and `JobQueue` (PostgreSQL) interfaces with tests
- [x] Worker with claim/lease/heartbeat/timeout/cancel and a no-op job
- [x] Schemas → Pydantic/TS generation; result envelope incl. `validation_status`, `calibration_status`, `engine_status`
- [x] Next.js skeleton + status page
- [x] Scientific-guard tests; `docs/third-party-licences.md`
- [x] `LICENSE` stays rights-reserved placeholder (ADR-0002)

## Phase 2 — AOI Input and Map Basics
Implemented 2026-10-04 (plan: `docs/phase-2-plan.md`, ADR-0012, evidence: `docs/phase-reports/phase-2.md`). **Awaiting owner acceptance.** Still no analysis of any kind.
- [ ] GitHub Actions run green on the Phase 2 commits (check after push)
- [x] AOI model + API: preview/create/upload/list/get/delete/limits
- [x] Coordinates + radius → polygon (geodesically correct)
- [x] Geometry validation, CRS normalisation (EPSG:4326 + working UTM), area limits. *Simplification not done: over-limit inputs are rejected, not simplified.*
- [x] Upload parsers: GeoJSON, KML, KMZ, zipped Shapefile (in-memory, hardened)
- [x] MapLibre 2D map: base map, draw rectangle/polygon/centre, display saved & uploaded AOI. *Vertex editing deferred (redraw instead, ADR-0012).*
- [x] Coordinate/radius input form (and rectangle/polygon numeric forms)
- [x] AOI persistence and reload
- [x] Tests: malformed/hostile uploads, antimeridian, self-intersections, huge AOIs

## Phase 3 — Remote Sensing Connectors
- [ ] Connector interface (inputs, outputs, quotas, caching, provenance)
- [ ] STAC connector (open catalogues) — Landsat, Sentinel-2, Sentinel-1 metadata/assets
- [ ] DEM connector (open DEM, e.g. Copernicus/SRTM — final choice via ADR)
- [ ] Geology / mineral-occurrence connector(s) (open datasets only)
- [ ] Google Earth Engine connector — **optional**, `ENABLE_EARTH_ENGINE=false` by default, experimental/non-commercial only, lazy import, no credentials in repo, never in CI (ADR-0004)
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
- [ ] **GATE: owner defines target country/region and pilot area before any Phase 5 design work (ADR-0003 amendment).** Then identify geology/structure/occurrence sources for them
- [ ] Engine design doc for **orogenic gold** (ADR-0003): evidence layers with citations, method (knowledge-driven / data-driven), limits; expert review
- [ ] Applicability gate (`applicable` / `not_applicable` / `applicability_unknown`)
- [ ] Evidence layer builders for the orogenic model (structure, host-lithology context, alteration proxies where bedrock exposed, geochemistry/geophysics if available)
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

## Decisions resolved (2026-10-04)
| # | Former question | Resolution |
|---|---|---|
| 1–2 | Licence | Private repo, rights reserved, no OSS licence (ADR-0001, 0002) |
| 3 | Deposit type | Orogenic gold only (ADR-0003) |
| 4 | Earth Engine | Optional; experimental/non-commercial only (ADR-0004) |
| 5 | Authentication | None in V1; local/private only (ADR-0005) |
| 6 | Object storage | Local filesystem; no MinIO (ADR-0006) |
| 7 | Queue | PostgreSQL-backed; no Redis (ADR-0007) |
| 8 | Limits | Conservative MVP limits (ADR-0008) |
| 9–10 | Science rules | Strict naming/envelope; no "confirmed" without field validation (ADR-0009, 0010) |

## Open Questions (require owner input)
3. **Target country/region and initial pilot area** — hard gate for Phase 5 design; not needed for Phases 1–2.
4. **Validation data** — known orogenic occurrences and cavity/void inventories the owner can supply (without these, all engines stay *experimental*).
5. **Earth Engine commercial eligibility** — account owner must validate in writing before any operational use (ADR-0004 amendment).
6. **Reference hardware** for profiling ADR-0008 limits (CPU/RAM/disk).
7. **Hosting target** — deferred; any non-local deployment is blocked by ADR-0005 until a new ADR.
