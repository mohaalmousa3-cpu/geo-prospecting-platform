# MASTER SPECIFICATION — geo-prospecting-platform (v0.2)

Version: **v0.2** (2026-10-04) · Status: **Living specification — Phases 0, 1, 2 and 2.5: implementation, verification and owner-acceptance records are listed separately in Current Project Status (acceptance reconciliation pending); Phase 3 planned but blocked pending prerequisite acceptance reconciliation, not started** · Governs all phases · Changes require an ADR (`docs/adr/`).

---

## Current Project Status

Updated 2026-10-04. **This is the single authoritative current-status record.** The Status column in §10 and the status banners in `README.md` and `TASKS.md` mirror it; on any difference this section governs, and superseded wording elsewhere is kept only as labelled historical notes. Detail and evidence: `TASKS.md`, `docs/phase-reports/` and the per-criterion matrix in `docs/phase-reports/acceptance-reconciliation.md`.

| Phase | Status |
|---|---|
| 0 Planning and scaffolding | Planning/scaffolding tasks recorded as done (`TASKS.md`); formal acceptance checklist reconciliation remains pending |
| 1 Repo/app foundation | Implemented — owner acceptance with follow-up checks recorded; checks reported complete (`docs/phase-reports/phase-1-closeout.md`); acceptance checklist reconciliation pending |
| 2 AOI input and map basics | Implemented — owner approval with follow-up items recorded (`docs/phase-reports/phase-2.md`); outstanding acceptance items remain open |
| 2.5 Structural hardening (projects, basemap provider abstraction, browser smoke test in CI) | Implemented — conditional owner approval recorded (two required follow-ups: browser smoke test in CI; default basemap `none`); required follow-ups reported implemented and tested (`docs/phase-reports/phase-2.5.md`); separate owner sign-off on the follow-ups is not recorded |
| 3 Remote-sensing data connectors | Planned — blocked pending prerequisite acceptance reconciliation; plan approved with constraints; implementation not started. |

**Reconciliation note (2026-10-04).** Three things are kept separate throughout: *implementation reported*, *verification evidence recorded*, and *explicit owner acceptance recorded*. Verification: CI run #7 on `02b6b05` (six jobs, including `e2e`) is **historical evidence** for the Phase 2.5 follow-ups. CI run #10 on `da90ce2`, the current committed HEAD, concluded `success` on all six jobs (read from GitHub on 2026-10-04); `02b6b05..da90ce2` changed documentation only. That is CI-level evidence for the committed baseline: it does not cover the uncommitted edits of this refresh, and it is not owner acceptance. A separate local verification of the *dirty working tree* on base `da90ce2` (lint, types, unit, integration, guards, schema drift, browser smoke test, Docker Compose startup, migrations, health, `noop` job, browser smoke test against the Compose stack) is recorded in `docs/phase-reports/acceptance-reconciliation.md`; it is **not** CI evidence for any committed SHA. Status records and checklists (`TASKS.md`, `README.md`, `docs/acceptance-criteria.md`, `docs/phase-reports/phase-2.5.md`) carry dated status notes mapping each item to its evidence; their checkboxes were **not** changed, and this documentation refresh does not close any outstanding acceptance gate. Approval of the Phase 3 plan is not acceptance of any earlier phase or of the Phase 2.5 follow-ups.

**Phase 3 — remote-sensing data connectors: blocked.** Planned — blocked pending prerequisite acceptance reconciliation; plan approved with constraints; implementation not started. The plan (`docs/phase-3-plan.md`) was approved by the owner with constraints; that approval is **not** authorization to start implementation. Beyond reconciliation and recorded acceptance of the prerequisite phases (including the Phase 2.5 follow-ups), implementation also needs an explicit start instruction. ADR-0014 is still **Proposed** (non-binding), and decision D8 (live-verification route) remains **open**.

Not implemented yet: any analysis, scoring, prospectivity, thermal, void, Earth Engine or 3D functionality. Phase 5 remains blocked until the owner defines the target country/region and pilot area (ADR-0003 amendment); Earth Engine remains blocked until the owner records commercial eligibility in writing (ADR-0004 amendment).

---

## 1. Project Purpose

Provide a web platform that, for a user-defined Area of Interest (AOI), gathers remote-sensing, geological, terrain and thermal data and produces **ranked, explained, uncertainty-aware prospectivity and anomaly layers** for:

- gold-related exploration targets,
- cavity/void-related targets,
- thermal anomalies.

The platform is a **decision-support and target-prioritisation tool**. It narrows where to spend field effort. It does not replace field verification.

## 2. Scope

### In scope
- AOI definition: coordinates + radius, drawn rectangle/polygon, upload of KML / KMZ / GeoJSON / zipped Shapefile.
- Data acquisition (free/open sources by default) for optical/multispectral, thermal, SAR/InSAR, DEM/terrain, geology and mineral-occurrence data.
- Per-theme processing pipelines: thermal, gold prospectivity, void evidence.
- 2D (MapLibre) and 3D (CesiumJS) visualisation of surface-referenced layers and targets.
- Ranked targets, each with explanation, confidence, uncertainty and full source/provenance metadata.
- Later: upload and interpretation of field geophysics (ERT, GPR, IP, magnetics).
- Reporting/export (GeoJSON, GeoPackage, PDF/HTML report).

### Out of scope (until explicitly approved)
- Claims of resource estimates, grades, tonnage, or reserves (JORC/NI 43-101-style statements).
- Subsurface depth estimates not derived from field geophysics or direct verification.
- Mobile apps, real-time streaming, multi-tenant billing.
- Paid data/services as a default dependency.
- Autonomous decision making about drilling, excavation or entry into caves/voids (safety-critical).
- Authentication, multi-user, public/hosted deployment (V1 is local/private only — ADR-0005).
- Gold deposit types other than orogenic (ADR-0003).
- MinIO/S3 storage and Redis (ADR-0006, ADR-0007).
- AOIs above the MVP limits (25 km²; ADR-0008).

### Accepted scope decisions (2026-10-04)
Binding; see `docs/adr/`. Private repository (0001) with rights reserved (0002); **orogenic gold is the only gold model** (0003); Earth Engine optional and experimental/non-commercial only (0004); no authentication in V1 (0005); local storage (0006); PostgreSQL-backed queue (0007); conservative AOI/compute limits — 25 km² AOI, 20 scenes, 1800 s jobs (0008); strict naming with mandatory confidence/uncertainty (0009); no "confirmed" gold/cavity wording without field validation (0010).

ADR authority, by recorded status:
- **Decided by the owner, Accepted:** ADR-0001–0011 (ADR-0011: shared package `geo_common` — contracts, abstractions and generic utilities only, never analysis logic — recorded on the owner's approval of T8).
- **Design decisions recorded within an owner-approved phase scope:** ADR-0012 (AOI input and validation; Phase 2; the ADR records that the owner may veto any point) and ADR-0013 (projects, basemap provider, derived CORS, browser smoke test in CI; Phase 2.5; owner scope, Claude design). They are in force as recorded; approval of the phase scope is not a separate explicit owner approval of every provision.
- **Proposed, non-binding:** ADR-0014 (connectors package, data assets).

## 3. Scientific Boundaries (normative)

Full text: `docs/scientific-constraints.md`. Summary — these are **MUST/MUST NOT** rules:

1. MUST NOT state or imply *confirmed* gold from satellite/remote data alone.
2. MUST NOT state or imply *confirmed* caves/voids from thermal or satellite data alone.
3. Satellite and thermal outputs are **prospectivity / anomaly layers**, never confirmation.
4. Subsurface depth MUST only be shown when derived from uploaded field geophysics or direct verification, and then labelled with method and uncertainty.
5. Every result MUST carry confidence and uncertainty.
6. Every target MUST carry a human-readable explanation and source metadata (dataset, version, acquisition date, processing steps, parameters, code version).
7. "Confirmed" status requires a field-validation record for the specific target (ADR-0010). In V1 every target is `validation_status = unvalidated`; the validation workflow is not built.
8. Gold prospectivity is **orogenic-only** with an applicability gate (ADR-0003); AOIs outside that setting get no score or capped confidence.
9. Language in UI, API, reports and code comments MUST use calibrated terms (see §3 of `docs/scientific-constraints.md`): "anomaly", "prospective", "consistent with", "requires field verification".

## 4. Core Workflows

### W1 — Define AOI
User enters lat/lon + radius, draws a rectangle/polygon, or uploads a file → backend validates, normalises to EPSG:4326 polygon (+ UTM working CRS), enforces size limits, stores AOI.

### W2 — Run analysis
User selects analysis themes (thermal / gold / void) and a time window → backend creates a **Job** → workers fetch data, run pipelines, write results + provenance → job status polled/streamed.

### W3 — Review results
Map shows layers with legends, uncertainty overlays and ranked targets. Selecting a target shows explanation, contributing evidence, confidence, uncertainty, sources, and the mandatory scientific disclaimer.

### W4 — 3D inspection
Targets/layers draped over 3D terrain (CesiumJS). Depth is shown **only** for geophysics-derived models (Phase 8+).

### W5 — Ingest field geophysics (Phase 8)
User uploads ERT/GPR/IP/magnetic data → format validation → processing/inversion via integrated libraries → results linked to AOI/targets, with inversion uncertainty and non-uniqueness warnings.

### W6 — Report & export
Reproducible report: inputs, parameters, sources, results, uncertainties, limitations, disclaimers.

## 5. Expected Inputs and Outputs

### Inputs
| Input | Formats / notes |
|---|---|
| AOI | lat/lon + radius (m/km); drawn polygon/rectangle; KML, KMZ, GeoJSON, Shapefile (.zip) |
| Time window | date range; season filters for thermal |
| Analysis themes | thermal, gold, void (subset) |
| Field geophysics (Phase 8) | ERT, GPR, IP, magnetic — formats to be fixed by ADR |
| User annotations (optional) | known occurrences, field observations (treated as evidence, flagged user-supplied) |

### Outputs
| Output | Description |
|---|---|
| Raster layers | LST anomaly, indices, prospectivity surface, uncertainty surface (COG) |
| Vector targets | polygons/points with rank, score, confidence, uncertainty, explanation, provenance |
| Explanations | structured (JSON) + rendered text; lists contributing evidence and counter-evidence |
| Provenance record | datasets, versions, dates, parameters, code commit, run id |
| Report | HTML/PDF + GeoJSON/GeoPackage export |

**Result envelope (all targets/layers):** `value`, `confidence` (categorical + numeric where meaningful), `uncertainty` (method-stated), `evidence[]`, `limitations[]`, `sources[]`, `disclaimer_id`. Schema lives in `packages/schemas/`.

## 6. Platform Architecture

Detail: `docs/architecture.md`.

- **Frontend**: Next.js (TypeScript), MapLibre GL JS (2D), CesiumJS (3D).
- **Backend API**: FastAPI (Python). Owns AOI, job, result, provenance APIs. No heavy compute in request handlers.
- **Workers**: Python background workers consuming a job queue; each engine is an isolated module with a typed interface.
- **Data**: PostgreSQL + PostGIS (metadata, vectors, provenance); rasters as COG on the **local filesystem** behind a `StorageBackend` interface (ADR-0006; no MinIO in V1).
- **Queue**: **PostgreSQL-backed job table** with `FOR UPDATE SKIP LOCKED` claiming, behind a `JobQueue` interface (ADR-0007; no Redis in V1).
- **Access model (V1)**: no authentication; local/private deployment only, loopback-bound (ADR-0005).
- **Shared schemas**: JSON Schema / OpenAPI as the single source of truth; generated TS and Pydantic types.
- **Infra**: Docker Compose for local/dev; production orchestration deferred to an ADR.

Principles: modular engines, explicit interfaces, reproducible runs, provenance by default, no secrets in repo, bounded compute per job.

## 7. Planned Engines (not implemented in foundation)

| Engine | Purpose | Candidate reuse |
|---|---|---|
| Ingest/AOI | Parse/validate/normalise geometries | GDAL/OGR, Shapely, pyproj, Fiona/pyogrio |
| Connectors | Fetch EO/DEM/geology data | STAC clients (pystac-client) and open APIs by default; Google Earth Engine optional, flagged, non-commercial only |
| Terrain | Slope, aspect, curvature, TPI, lineaments, drainage | GDAL, WhiteboxTools, RichDEM |
| Thermal | LST retrieval, anomaly detection, temporal stability | Landsat LST workflows (Collection 2 ST products) |
| Deformation | InSAR time series (optional, heavy) | MintPy (input from ISCE/ARIA/HyP3 products) |
| Gold prospectivity | **Orogenic-gold** evidence layers → weights/ML → prospectivity + uncertainty, behind an applicability gate | EIS Toolkit, EnMAP-Box concepts, scikit-learn |
| Void evidence | Multi-evidence integration (terrain, thermal, deformation, geology) | custom, with EIS Toolkit patterns |
| Geophysics | ERT/IP/GPR/magnetics processing and inversion | ResIPy, pyGIMLi, GPRPy |
| Geological modelling | 3D geological model from constraints (Phase 8+, optional) | GemPy |
| Scoring/Explain | Ranking, confidence, uncertainty, explanations | custom |

Each engine MUST document inputs, outputs, assumptions, validity limits and failure modes before implementation (`workers/<engine>/README.md`).

## 8. Visualisation Goals

- **2D**: AOI editor; base maps; toggleable layers; opacity; legends; uncertainty overlay; target list ↔ map linking; provenance panel.
- **3D**: terrain with draped layers and targets; vertical exaggeration control; geophysics sections/volumes only when data exist.
- **Honesty in UI**: colour ramps and labels must not imply certainty; low-confidence results visually distinct; disclaimer always reachable from any target.
- **Accessibility**: colour-blind-safe palettes; keyboard operable controls where feasible.

## 9. Open-Source Reuse Strategy

Detail: `docs/dependency-strategy.md`.

- Prefer **integrating via libraries/CLI in isolated worker images** over copying code.
- Respect licences (several candidate tools are GPL/EUPL — copyleft implications must be reviewed *before* adoption; see risk register).
- EnMAP-Box is a QGIS plugin; reuse its **concepts and underlying libraries** (e.g. hub-datacube / qgis-independent parts where available), not its GUI.
- Pin versions, record them in provenance, wrap each third-party tool behind an internal interface so it can be swapped.
- Heavy/optional tools (MintPy, GemPy) run in separate worker images and are disabled by default.

## 10. Phased Build Plan

Authoritative checklist: `TASKS.md`. Acceptance: `docs/acceptance-criteria.md`. The Status column below mirrors *Current Project Status* at the top of this document, which governs on any difference.

| Phase | Theme | Status (2026-10-04) |
|---|---|---|
| 0 | Planning and scaffolding | Planning/scaffolding tasks recorded as done; acceptance checklist reconciliation pending |
| 1 | Repo/app foundation (running skeleton, CI, DB) | Implemented — owner acceptance with follow-up checks recorded; checks reported complete; checklist reconciliation pending |
| 2 | AOI input and map basics | Implemented — owner approval with follow-up items recorded; outstanding acceptance items remain open |
| 2.5 | Structural hardening (projects, basemap provider abstraction, browser smoke test in CI) | Implemented — conditional owner approval recorded; required follow-ups reported implemented and tested; separate owner sign-off on follow-ups not recorded |
| 3 | Remote sensing connectors | Planned — blocked pending prerequisite acceptance reconciliation; plan approved with constraints; implementation not started. |
| 4 | Thermal pipeline | Planned |
| 5 | Gold prospectivity pipeline | Planned — blocked until target region and pilot area are defined |
| 6 | Void evidence pipeline | Planned |
| 7 | 3D visualisation | Planned |
| 8 | Field geophysics ingestion | Planned |
| 9 | Confidence, uncertainty and reporting refinement | Planned |

Rules: one phase at a time; no phase starts until the previous phase's acceptance criteria are met and recorded; scope creep is deferred to the backlog.

## 11. Acceptance Philosophy

- Acceptance is **evidence-based**: tests, reproducible runs, and documented validation — not demos.
- **Scientific acceptance** is separate from functional acceptance: a pipeline that runs but is unvalidated is marked *experimental* and cannot present results as reliable.
- Validation against known sites/benchmarks (with documented limitations) is required before a pipeline leaves *experimental* status.
- Negative results and "insufficient data" are first-class outputs.
- A feature that makes the platform *appear* more certain than the evidence warrants is a defect, regardless of functionality.

## 12. Glossary

- **AOI** — Area of Interest.
- **Prospectivity** — relative likelihood ranking under stated evidence; not a probability of occurrence unless calibrated and validated.
- **Anomaly** — statistically/spatially distinct signal; cause unproven.
- **Verification** — direct field evidence (sampling, drilling, survey, inspection).
