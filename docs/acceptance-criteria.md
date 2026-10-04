# Acceptance Criteria

A phase is **accepted** only when all criteria are met, evidence is recorded (test output, run logs, notes), and the user confirms. Scientific criteria are assessed separately from functional ones.

**Universal criteria (every phase):**
- U1. All new code has tests; test suite passes in CI; no skipped/disabled tests.
- U2. Linting/type checks pass.
- U3. No secrets or large data committed; `.env.example` updated for new config.
- U4. Docs updated (README of touched dirs, architecture/ADR if applicable).
- U5. Scientific guard tests pass (no forbidden claims; envelope completeness; depth gating).
- U6. Compute bounded and documented (limits, timeouts).
- U7. Licence check done for any new dependency.

---

## Phase 0 — Planning and scaffolding
- [ ] All files listed in the Phase 0 brief exist and are internally consistent.
- [ ] Scientific constraints documented and referenced from README, MASTER_SPEC, CLAUDE.
- [ ] Open questions listed with owner decisions pending.
- [ ] No application code or scientific logic present.
- [ ] User review completed.

## Phase 1 — Repo/app foundation
Evidence: `docs/phase-reports/phase-1.md`. Owner acceptance still required.
- [x] `docker compose up` starts postgis, backend, worker, frontend from a clean clone (no Redis, no MinIO); ports bound to 127.0.0.1.
- [x] `/api/v1/health` returns OK; frontend status page shows backend health.
- [x] Alembic migrations apply cleanly; PostGIS extension enabled; initial tables created.
- [x] A no-op job travels API → `job` table → worker → DB with correct status transitions.
- [x] Queue integration tests pass: concurrent claim (no double-claim), lease expiry recovery, attempt limit, hard timeout kill, cancellation, `MAX_QUEUED_JOBS` enforcement.
- [x] `StorageBackend` local implementation rejects path traversal and absolute keys (tested).
- [x] Result envelope requires `validation_status`, `calibration_status`, `engine_status`; `validation_status` accepts only `unvalidated`.
- [ ] Forbidden-term scan (ADR-0009) runs in CI over source, fixtures and UI strings, with a documented docs allow-list.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] No authentication code, Redis, or MinIO present; README states local/private-only.
- [ ] Schema pipeline generates Pydantic and TS types from `packages/schemas`; CI fails on drift.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] Result envelope schema rejects objects missing confidence/uncertainty/explanation/sources (tested).
- [ ] CI runs lint, type-check, tests, secret scan.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] `LICENSE` remains the rights-reserved placeholder (ADR-0002); `docs/third-party-licences.md` exists and lists all Phase 1 dependencies.


## Phase 2 — AOI input and map basics
Evidence: `docs/phase-reports/phase-2.md`. Owner acceptance still required.
- [x] Coordinates+radius produce a geodesically correct polygon (tested against reference values).
- [x] Draw rectangle/polygon on map; AOI saved and reloaded.
- [x] Upload of GeoJSON, KML, KMZ, zipped Shapefile accepted; invalid/hostile files rejected with clear errors (zip-bomb, path traversal, bad CRS, empty, self-intersecting, oversize).
- [ ] AOI normalised to EPSG:4326 + working UTM CRS; ADR-0008 limits enforced server-side and configurable, with boundary tests at, just below and just above each limit (area 25 km², radius 2.5 km, min 0.01 km², vertices, upload size, archive size/file count).  *(Implemented; boundary tests at/just-below/just-above exist for area, min area, radius and vertices. Upload size and archive size/count have rejection tests only above the limit, not at/just below — hence not ticked.)*
- [x] Antimeridian/polar edge cases handled or explicitly rejected.
- [x] No analysis results shown in this phase.

## Phase 3 — Remote sensing connectors
- [ ] Connector interface implemented with at least STAC (imagery metadata/assets) and one open DEM source.
- [ ] Each fetch records provenance (dataset, version, date, licence, URL, checksum).
- [ ] Caching works (second identical request makes no external call; tested).
- [ ] Request budgets/quotas enforced; clear errors on exceed.
- [ ] CI uses recorded fixtures only; no live network calls in tests.
- [ ] Earth Engine connector, if present, is flag-disabled by default (`ENABLE_EARTH_ENGINE=false`), imports EE lazily, contains no credentials, is never used in CI, records `via: earth_engine` in provenance, and the platform passes all tests with it disabled (ADR-0004).
- [ ] Missing-coverage/cloudy cases yield `insufficient_data`, not silent defaults.

## Phase 4 — Thermal pipeline
- [ ] Engine design doc approved (method, assumptions, limits, citations).
- [ ] LST computed from Landsat C2 L2 ST; masking applied; results match reference values on a documented test scene within stated tolerance.
- [ ] Anomaly output includes uncertainty raster and confidence; single-date results capped at low confidence.
- [ ] Temporal persistence analysis implemented and documented.
- [ ] Confounders (slope/aspect, season, land cover) addressed or explicitly listed as limitations in output.
- [ ] Output named/labelled as anomaly; no void/gold claims.
- [ ] Engine flagged *experimental* until validated.

## Phase 5 — Gold prospectivity pipeline
- [ ] Deposit model is **orogenic gold** (ADR-0003), recorded as `deposit_model` in every result; no other deposit type is implied anywhere in UI/API/docs.
- [ ] Applicability gate implemented and tested: `not_applicable` → no score; `applicability_unknown` → confidence capped at low.
- [ ] Target region(s) fixed and geology/structure sources identified for them before design-doc approval.
- [ ] Evidence layers documented with rationale and citations.
- [ ] Prospectivity + uncertainty surfaces produced; scores labelled uncalibrated unless calibrated.
- [ ] Validation performed with spatial cross-validation on available known occurrences; metrics and limitations documented (or engine remains *experimental*).
- [ ] Each target has rank, explanation (supporting + counter-evidence), confidence, uncertainty, sources.
- [ ] Language audit: no "gold found/confirmed".
- [ ] Domain-expert review recorded.

## Phase 6 — Void evidence pipeline
- [ ] Engine design doc approved; each evidence type's limits stated.
- [ ] Output is `void_evidence_score`; no "cave/void detected" strings anywhere.
- [ ] Lithological/plausibility gating implemented and documented.
- [ ] Targets list counter-evidence and alternative explanations.
- [ ] Safety statement present; no entry/excavation guidance.
- [ ] Optional InSAR path off by default; heavy deps isolated.
- [ ] Validation on documented sites where data exist; otherwise *experimental*.

## Phase 7 — 3D visualisation
- [ ] CesiumJS renders terrain and drapes layers/targets for an AOI without requiring a paid token by default.
- [ ] Uncertainty/confidence visible in 3D; disclaimer reachable.
- [ ] Automated check: no depth or sub-surface geometry rendered without `depth_basis` ∈ {field_geophysics, direct_verification}.
- [ ] Performance budget met on documented reference hardware (e.g. interactive frame rate for the max AOI).
- [ ] Graceful degradation when WebGL unavailable.

## Phase 8 — Field geophysics ingestion
- [ ] Supported formats documented per method; sample fixtures tested.
- [ ] Uploads validated (format, geometry, units, CRS, metadata completeness).
- [ ] ERT/IP and GPR processing reproduce results of upstream-tool reference examples within tolerance.
- [ ] Inversion outputs show depth of investigation, regularisation parameters, misfit, non-uniqueness warning.
- [ ] Depth displayed only for geophysics-derived results, with D-2 disclaimer and uncertainty.
- [ ] Link between geophysics and targets is explicit, and does not upgrade a target to "confirmed".
- [ ] Heavy/optional tools (GemPy) isolated and off by default.

## Phase 9 — Confidence, uncertainty and reporting refinement
- [ ] Single documented methodology for confidence & uncertainty used across engines.
- [ ] Calibration assessed where validation data exist; otherwise outputs labelled uncalibrated.
- [ ] Reports reproducible from stored provenance (re-run yields equivalent results within tolerance).
- [ ] Report includes inputs, sources, parameters, results, uncertainty, limitations, disclaimers.
- [ ] Full language audit passed (UI, API, reports, docs).
- [ ] Documented scaling limits and cost estimates; security review completed.
- [ ] Engines either validated (with expert sign-off) or remain visibly *experimental*.

---

## Scientific acceptance (applies to Phases 4–9)
- S1. Method documented with citations; assumptions and validity range stated.
- S2. Validation approach and outcome documented, including failures.
- S3. Known failure modes surfaced to the user in explanations.
- S4. Expert (geoscientist) review recorded, or status = *experimental*.
