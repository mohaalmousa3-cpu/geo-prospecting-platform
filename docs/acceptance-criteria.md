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
- [ ] `docker compose up` starts postgis, redis, backend, worker, frontend from a clean clone.
- [ ] `/api/v1/health` returns OK; frontend status page shows backend health.
- [ ] Alembic migrations apply cleanly; PostGIS extension enabled; initial tables created.
- [ ] A no-op job travels API → queue → worker → DB with correct status transitions.
- [ ] Schema pipeline generates Pydantic and TS types from `packages/schemas`; CI fails on drift.
- [ ] Result envelope schema rejects objects missing confidence/uncertainty/explanation/sources (tested).
- [ ] CI runs lint, type-check, tests, secret scan.
- [ ] Licence decision recorded (ADR) and `LICENSE` added.

## Phase 2 — AOI input and map basics
- [ ] Coordinates+radius produce a geodesically correct polygon (tested against reference values).
- [ ] Draw rectangle/polygon on map; AOI saved and reloaded.
- [ ] Upload of GeoJSON, KML, KMZ, zipped Shapefile accepted; invalid/hostile files rejected with clear errors (zip-bomb, path traversal, bad CRS, empty, self-intersecting, oversize).
- [ ] AOI normalised to EPSG:4326 + working UTM CRS; area limits enforced and configurable.
- [ ] Antimeridian/polar edge cases handled or explicitly rejected.
- [ ] No analysis results shown in this phase.

## Phase 3 — Remote sensing connectors
- [ ] Connector interface implemented with at least STAC (imagery metadata/assets) and one open DEM source.
- [ ] Each fetch records provenance (dataset, version, date, licence, URL, checksum).
- [ ] Caching works (second identical request makes no external call; tested).
- [ ] Request budgets/quotas enforced; clear errors on exceed.
- [ ] CI uses recorded fixtures only; no live network calls in tests.
- [ ] Earth Engine connector, if present, is flag-disabled by default, and contains no credentials.
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
- [ ] Deposit type(s) in scope chosen by the user and documented; model invalid outside scope is flagged.
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
