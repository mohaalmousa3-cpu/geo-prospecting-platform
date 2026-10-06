# MASTER SPECIFICATION — geo-prospecting-platform (v0.2)

Version: **v0.2** (2026-10-04) · Status: **Living specification — Phases 0, 1, 2 and 2.5: implementation, verification and owner-acceptance records are listed separately in Current Project Status (owner decisions of 2026-10-05 recorded); Phase 3 not started (ADR-0014 Accepted 2026-10-05; blocked pending a separate bounded start instruction; D8 strategy resolved, live-verification readiness pending)** · Governs all phases · Changes require an ADR (`docs/adr/`).

---

## Current Project Status

Updated 2026-10-05. **This is the single authoritative current-status record.** The Status column in §10 and the status banners in `README.md` and `TASKS.md` mirror it; on any difference this section governs, and superseded wording elsewhere is kept only as labelled historical notes. Detail and evidence: `TASKS.md`, `docs/phase-reports/` and the per-criterion matrix in `docs/phase-reports/acceptance-reconciliation.md`.

| Phase | Status |
|---|---|
| 0 Planning and scaffolding | Accepted by the owner within the historical planning/scaffolding scope (decision D-2, 2026-10-05; confirmed 2026-10-05). **Documented follow-up F-1 stays open** (non-blocking for fixtures-only Phase 3a by the owner's narrow exception of 2026-10-05; must close before any live connector slice): the checklist item *all files exist and are internally consistent* is not claimed complete, and the acceptance is not evidence that the current documents are free of contradictions |
| 1 Repo/app foundation | Implemented — owner acceptance with follow-up checks recorded; the reported evidence (CI run #3 `bbab3c8` and later; clean-checkout Compose run for `5ac5a27`) accepted by owner decision D-3 (2026-10-05); the three open checklist items and the `TASKS.md` CI box are ticked (`docs/phase-reports/phase-1-closeout.md`) |
| 2 AOI input and map basics | Implemented — owner approval with follow-up items recorded (`docs/phase-reports/phase-2.md`); the upload/archive boundary-test gap accepted as closed by owner decision D-4 (2026-10-05; evidence: CI run #11 on `5ac5a27`); the composite CRS/limits checklist box is ticked with each aspect tied to its evidence; the `TASKS.md` box on GitHub Actions is ticked on the owner's approval (2026-10-05) with clarified wording — runs #4 (`2ddef67`) and #5 (`1e7c823`); commit `46596b4` had no independent run |
| 2.5 Structural hardening (projects, basemap provider abstraction, browser smoke test in CI) | Implemented — owner acceptance of the two required follow-ups (browser smoke test in CI; default basemap `none`) and of the derived-CORS addition recorded by owner decision D-1 (2026-10-05); the Phase 2.5 acceptance gate is closed. Scope: the documented behaviour — not exhaustive UI interactions or runtime-displayed text (`docs/phase-reports/phase-2.5.md`) |
| 3 Remote-sensing data connectors | **Update 2026-10-05 (owner start instruction): Phase 3a (fixtures-only) is authorised checkpoint by checkpoint — CP1 (connector skeleton), CP2 (migration 0004, AOI-bound enqueue, r5 deletion rewrite) and CP3 (migration 0005, assets, publication protocol, results guard, tombstones) on branch `claude/phase-3a-fixtures`, base `6b8d15e` — in progress, not complete, not accepted; slices 3b onward not started; each checkpoint stops for the owner's review.** Earlier status, kept as history: planned; ADR-0014 Accepted 2026-10-05 (r5 deletion amendment accepted; implemented only as far as the first checkpoint's connector skeleton); the fixtures-only Phase 3a scope accepted as scope; a separate bounded start instruction was required (now given for the first checkpoint); D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved. |

**Reconciliation note (2026-10-05).** Three things are kept separate throughout: *implementation reported*, *verification evidence recorded*, and *explicit owner acceptance recorded*. Owner acceptance: the owner's decisions D-1…D-6 of 2026-10-05 are transcribed faithfully (they are transcriptions, not independent signed records) in `docs/phase-reports/acceptance-reconciliation.md` §2; only the checkboxes and statuses those decisions support were updated. Verification: CI run #11 on `5ac5a278a9b93aaab4877e7ef84aa2640ff94b7c` (https://github.com/mohaalmousa3-cpu/geo-prospecting-platform/actions/runs/37222835783) concluded `success` on all six jobs (including `e2e` and the rewritten dependency-audit job) — CI evidence for that commit; a Docker Compose run (migrations, health, `noop` job, browser smoke test) from a clean checkout of the same commit is **locally reported** evidence, not CI. CI run #7 on `02b6b05` and run #10 on `da90ce2` are **historical evidence** for earlier commits. The documentation-only commit that records the 2026-10-05 decisions has its own CI result, which is not recorded in the repository (a commit cannot cite its own run). Acceptance of earlier phases is not authorization to start Phase 3.

**Phase 3 — remote-sensing data connectors: Phase 3a first checkpoint authorised; everything else blocked.** **Update 2026-10-05 (owner start instruction): Phase 3a (fixtures-only) is authorised checkpoint by checkpoint — CP1 (connector skeleton), CP2 (migration 0004, AOI-bound enqueue, r5 deletion rewrite) and CP3 (migration 0005, assets, publication protocol, results guard, tombstones) on branch `claude/phase-3a-fixtures`, base `6b8d15e` — in progress, not complete, not accepted; slices 3b onward not started; each checkpoint stops for the owner's review.** Earlier status, kept as history: planned; ADR-0014 Accepted 2026-10-05 (r5 deletion amendment accepted; implemented only as far as the first checkpoint's connector skeleton); the fixtures-only Phase 3a scope accepted as scope; a separate bounded start instruction was required (now given for the first checkpoint); D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved. The plan (`docs/phase-3-plan.md`) was approved by the owner with constraints; neither that approval nor the acceptance of the earlier phases is authorization to start implementation. Gates that remain: (1) an independent, explicit, bounded start instruction (the owner intends Phase 3a only) — the outstanding gate for the fixtures-only slice (the start instruction should also state the implementation branch/base, see `docs/phase-3-plan.md` §6); ADR-0014 is **Accepted** (2026-10-05, not implemented; conditions in the ADR's *Owner decision record*) and the fixtures-only 3a scope (`docs/phase-3-plan.md` §6) was accepted as scope; (2) for any **live** slice additionally: F-1 closed, D8 live-verification readiness (official-source confirmation of endpoints/hosts, terms, licences, attribution, request limits and costs; approved exact host/port allowlist; approved application and network controls; HTTP-client selection and licence review), a start instruction for that slice, and a recorded live-verification report before the slice is accepted. D8's *strategy* is resolved (option D: 3a fixtures-only; live verification mandatory before accepting live connector slices 3b and DEM; route B preferred subject to separate approval of the exact host allowlist, otherwise route A). No host name and no network control is approved.

**Owner exception (2026-10-05, narrow):** the owner designated F-1 a **non-blocking documentation follow-up for the fixtures-only Phase 3a slice only**. It is not a general change to the phase-start rules and not a declaration that F-1 is satisfied. F-1 stays **open**; its known unresolved issues are listed in `docs/phase-reports/acceptance-reconciliation.md` §9a; **F-1 must be closed before any live connector slice may be authorised**. The exception does **not** authorise Phase 3a to start.

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
- **Design decisions recorded within an owner-approved phase scope:** ADR-0012 (AOI input and validation; Phase 2; the ADR records that the owner may veto any point) and ADR-0013 (projects, basemap provider, derived CORS, browser smoke test in CI; Phase 2.5; owner scope, Claude design). They are in force as recorded; approval of the phase scope is not a separate explicit owner approval of every provision. The one explicit exception: the ADR-0013 follow-up amendment (default basemap `none`, derived CORS, browser smoke test in CI) was explicitly accepted by the owner on 2026-10-05 (D-1), within its documented scope.
- **Decided by the owner, Accepted 2026-10-05 — implementation limited to the Phase 3a first checkpoint (connector skeleton):** ADR-0014 (connectors package, `data_asset`, job↔project/AOI linkage; conditions in its *Owner decision record*; acceptance is not a start instruction for Phase 3 or 3a).

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
| 0 | Planning and scaffolding | Accepted within the historical planning/scaffolding scope (D-2, 2026-10-05); *internally consistent* item open |
| 1 | Repo/app foundation (running skeleton, CI, DB) | Implemented — owner acceptance with follow-up checks recorded; open checks accepted on evidence (D-3, 2026-10-05) |
| 2 | AOI input and map basics | Implemented — owner approval with follow-up items recorded; upload/archive boundary gap closed (D-4, 2026-10-05); the `TASKS.md` "Actions green" item ticked with clarified wording (runs #4/#5; `46596b4` had no independent run) |
| 2.5 | Structural hardening (projects, basemap provider abstraction, browser smoke test in CI) | Implemented — follow-ups and derived-CORS addition accepted by the owner (D-1, 2026-10-05); acceptance gate closed |
| 3 | Remote sensing connectors | **Update 2026-10-05 (owner start instruction): Phase 3a (fixtures-only) is authorised checkpoint by checkpoint — CP1 (connector skeleton), CP2 (migration 0004, AOI-bound enqueue, r5 deletion rewrite) and CP3 (migration 0005, assets, publication protocol, results guard, tombstones) on branch `claude/phase-3a-fixtures`, base `6b8d15e` — in progress, not complete, not accepted; slices 3b onward not started; each checkpoint stops for the owner's review.** Earlier status, kept as history: planned; ADR-0014 Accepted 2026-10-05 (r5 deletion amendment accepted; implemented only as far as the first checkpoint's connector skeleton); the fixtures-only Phase 3a scope accepted as scope; a separate bounded start instruction was required (now given for the first checkpoint); D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved. |
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
