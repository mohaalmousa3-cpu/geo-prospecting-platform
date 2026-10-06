# Acceptance Criteria

A phase is **accepted** only when all criteria are met, evidence is recorded (test output, run logs, notes), and the user confirms. Scientific criteria are assessed separately from functional ones.

> **Status note (2026-10-04, documentation reconciliation).** In this file `[x]` means *implementation reported and verified when recorded in the phase report*; it is **not** owner acceptance, which is tracked separately in the phase reports and in `MASTER_SPEC.md` (Current Project Status). The dated notes below annotate evidence. Checkboxes were left unchanged until the owner's decisions of 2026-10-05 (D-2, D-3, D-4, transcribed in `docs/phase-reports/acceptance-reconciliation.md` §2); afterwards **only the boxes named in the 2026-10-05 notes below were ticked**, and every other box is unchanged. CI evidence is scoped to the named commit and jobs (workflow `ci`, branch `claude/geo-prospecting-foundation-hmcma4`, read from GitHub on 2026-10-04): #1 `823fa87` failed; #2 `eda2681` failed; #3 `bbab3c8` success; #4 `2ddef67` success; #5 `1e7c823` success; #6 `46178de` success; #7 `02b6b05` success (six jobs incl. `e2e`) — **historical evidence** for the Phase 2.5 follow-ups; #8 `9a7947e` cancelled (superseded); #9 `c3cf3a3` success; #10 `da90ce2` success (six jobs incl. `e2e`; documentation-only delta from #7); #11 `5ac5a27` success (six jobs incl. `e2e` and the rewritten `audit` job; CI evidence for that commit; https://github.com/mohaalmousa3-cpu/geo-prospecting-platform/actions/runs/37222835783). CI runs lint, types, unit, integration, guards, licence register, frontend, schema drift, gitleaks, a docker *build* and the browser smoke test; it does not run `docker compose up`, and its dependency-audit job is report-only.

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
> **F-1 status (2026-10-06): partially reconciled; not closed** — `docs/phase-reports/acceptance-reconciliation.md` §9b (remaining: F1-8 only; F1-1 and F1-7 resolved 2026-10-06); the box below stays open.
> Status note (2026-10-04): evidence — the Phase 0 documents exist at HEAD (listed), and `scientific-constraints.md` is referenced from README, MASTER_SPEC and CLAUDE.md. Boxes left open: (a) *internally consistent* — status inconsistencies were found during this reconciliation and are annotated, not resolved; (b) *no application code* — true at the Phase 0 commit `ca2d4e4`, superseded by design from Phase 1, so it cannot be evaluated at HEAD and needs an owner decision (satisfied-at-`ca2d4e4`); (c) *user review completed* — owner decisions are transcribed in ADR-0001…0010 and `TASKS.md`, but no explicit Phase 0 acceptance statement is recorded. **Update 2026-10-05 (D-2):** the owner considers *no application code* satisfied **at `ca2d4e4`** (not a condition on today's HEAD) and accepts Phase 0 within its historical planning/scaffolding scope. Ticked: *constraints documented and referenced* (verified by `grep`), *open questions listed* (`TASKS.md`), *no application code* (as of `ca2d4e4`), *user review completed* (D-2). **Left open:** *all files exist and are internally consistent* — the files exist, but the owner explicitly did not accept this as proof that the current documents are free of contradictions. **Follow-up (2026-10-05, owner):** the open item stays open as documented follow-up F-1 (documentation consistency); it is not claimed complete. **Owner exception (2026-10-05):** F-1 is a non-blocking documentation follow-up for fixtures-only Phase 3a only; it stays open, its known issues are in `acceptance-reconciliation.md` §9a, and it must be closed before any live connector slice is authorised.

- [ ] All files listed in the Phase 0 brief exist and are internally consistent.
- [x] Scientific constraints documented and referenced from README, MASTER_SPEC, CLAUDE.
- [x] Open questions listed with owner decisions pending.
- [x] No application code or scientific logic present.
- [x] User review completed.

## Phase 1 — Repo/app foundation
Evidence: `docs/phase-reports/phase-1.md`. Owner acceptance still required.
> Status note (2026-10-04): the sentence above is historical; owner acceptance **with follow-up checks** is recorded (`phase-1-closeout.md`). Evidence for the three open boxes (not ticked, per the governance decision; ticking is the owner's reconciliation call): all map to CI run #3 on `bbab3c8` (`success`) and later runs. (i) *forbidden-term scan*: CI step "Scientific guards" (`pytest tests/scientific`); the scanner config (`tests/scientific/forbidden_terms.py`) scans repo files by suffix with a docs allow-list — its coverage of user-visible strings is analysed, with gaps, in `docs/phase-reports/acceptance-reconciliation.md` §6 (a passing guard is not proof that every UI string is covered). (ii) *schema pipeline/drift*: frontend-job step "Generated schema types must match packages/schemas" passed; run #2 failed on generated-code drift, showing the check does fail on drift. (iii) *CI runs lint, type-check, tests, secret scan*: steps ruff check, ruff format, mypy, unit, integration, guards and gitleaks passed in run #3. **Update 2026-10-05 (D-3):** the owner accepted the reported evidence as sufficient for the three open boxes; they are ticked. For the forbidden-term box this means "the guard runs in CI over repository source text" with the documented limits of `docs/phase-reports/acceptance-reconciliation.md` §6 (source scan only; not a proof of rendered-DOM or every-language coverage), as the owner kept in D-5.
- [x] `docker compose up` starts postgis, backend, worker, frontend from a clean clone (no Redis, no MinIO); ports bound to 127.0.0.1.
- [x] `/api/v1/health` returns OK; frontend status page shows backend health.
- [x] Alembic migrations apply cleanly; PostGIS extension enabled; initial tables created.
- [x] A no-op job travels API → `job` table → worker → DB with correct status transitions.
- [x] Queue integration tests pass: concurrent claim (no double-claim), lease expiry recovery, attempt limit, hard timeout kill, cancellation, `MAX_QUEUED_JOBS` enforcement.
- [x] `StorageBackend` local implementation rejects path traversal and absolute keys (tested).
- [x] Result envelope requires `validation_status`, `calibration_status`, `engine_status`; `validation_status` accepts only `unvalidated`.
- [x] Forbidden-term scan (ADR-0009) runs in CI over source, fixtures and UI strings, with a documented docs allow-list.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] No authentication code, Redis, or MinIO present; README states local/private-only.
- [x] Schema pipeline generates Pydantic and TS types from `packages/schemas`; CI fails on drift.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] Result envelope schema rejects objects missing confidence/uncertainty/explanation/sources (tested).
- [x] CI runs lint, type-check, tests, secret scan.  *(implemented and passing locally via `make ci`; GitHub Actions run pending — see phase report)*
- [x] `LICENSE` remains the rights-reserved placeholder (ADR-0002); `docs/third-party-licences.md` exists and lists all Phase 1 dependencies.


## Phase 2 — AOI input and map basics
Evidence: `docs/phase-reports/phase-2.md`. Owner acceptance still required.
> Status note (2026-10-04): the sentence above is historical; owner approval **with follow-up items** is recorded (`phase-2.md`). The open box stays open: boundary tests at/just-below/just-above exist for area, min area, radius and vertices; for upload size and archive size/count only above-limit rejection tests were recorded when this box was left open (`apps/backend/tests/test_aoi_api.py`). Update 2026-10-04: boundary tests for each of those three limits (just below / exactly at / just above, per the ADR-0012 §8 semantics) now exist in `apps/backend/tests/test_aoi_upload_limits.py` and pass locally on the dirty working tree on base `da90ce2`; they are **uncommitted**, so they are not CI evidence, and the box stays unticked (owner decision). CI for the Phase 2 commits: `2ddef67` (#4) and `1e7c823` (#5) `success`; `46596b4` has no run of its own. Phase 2's UI delete claim was amended by the Phase 2.5 CORS finding. **Update 2026-10-05 (D-4):** the owner accepted the upload/archive boundary-test gap as closed (evidence: 24 tests, committed, green in CI run #11 on `5ac5a27`). The composite box is ticked only because every aspect has its own evidence: *normalised to EPSG:4326* — reprojection from EPSG:32632 and persisted `ST_SRID = 4326`, valid geometry (`test_aoi_parsers.py`, `test_aoi_api.py`); *working UTM CRS* — `test_utm_zone` cases and the stored working CRS (`test_aoi_geometry.py`); *limits enforced server-side and configurable* — settings-driven limits exercised through the API (`MAX_AOI_AREA_KM2`, `MAX_UPLOAD_MB`, `MAX_ARCHIVE_*`, `MAX_STORED_AOIS`); *boundary tests below/at/above* — area, min area, radius, vertices (existing) and upload size, archive size, archive entries (new). Not claimed: reprojection from CRSs other than EPSG:32632 (still untested, risk P-10).
- [x] Coordinates+radius produce a geodesically correct polygon (tested against reference values).
- [x] Draw rectangle/polygon on map; AOI saved and reloaded.
- [x] Upload of GeoJSON, KML, KMZ, zipped Shapefile accepted; invalid/hostile files rejected with clear errors (zip-bomb, path traversal, bad CRS, empty, self-intersecting, oversize).
- [x] AOI normalised to EPSG:4326 + working UTM CRS; ADR-0008 limits enforced server-side and configurable, with boundary tests at, just below and just above each limit (area 25 km², radius 2.5 km, min 0.01 km², vertices, upload size, archive size/file count).  *(Implemented; boundary tests at/just-below/just-above exist for area, min area, radius and vertices. Upload size and archive size/count have rejection tests only above the limit, not at/just below — hence not ticked.)*
- [x] Antimeridian/polar edge cases handled or explicitly rejected.
- [x] No analysis results shown in this phase.

## Phase 2.5 — Structural hardening (projects, basemap abstraction)
Evidence and the owner checklist: `docs/phase-reports/phase-2.5.md`. Owner acceptance still required.
> Status note (2026-10-04): conditional owner approval is recorded (two required follow-ups). The `[x]` items below are implementation + verification; the *(follow-up)* items are reported implemented and tested. Run #7 on `02b6b05` is **historical evidence**; run #10 on `da90ce2` (current committed HEAD) succeeded on six jobs incl. `e2e`. "Owner acceptance still required" remains accurate for the follow-ups: a separate owner sign-off on them is not recorded, and the owner-tick checklist in `phase-2.5.md` §4 is intentionally unticked. **Update 2026-10-05 (D-1):** the owner accepted the two follow-ups and the derived-CORS addition within their documented scope, closing the Phase 2.5 acceptance gate; this does not claim exhaustive UI-interaction or runtime-displayed-text coverage. No box in this section needed ticking (all were already `[x]`).
- [x] `project` entity with bounded count; every AOI belongs to one project; migration preserves existing AOIs (tested).
- [x] Contracts, persistence and API updated; saving requires `project_id`, preview does not; deletion of a non-empty project needs explicit `delete_aois=true`.
- [x] Smallest project-aware UI flow verified in unit tests and in a real browser.
- [x] Basemap provider abstraction (`osm`/`xyz`/`none`) with validation, fallback warning and privacy note.
- [x] Project/AOI/future-jobs/outputs relationships documented (`docs/data-model.md`, ADR-0013).
- [x] AOI validation and upload hardening unchanged (suites intact; hostile and over-limit input still rejected with a valid project).
- [x] No analysis, scoring, Earth Engine, 3D or auth expansion.
- [x] *(follow-up)* Browser smoke test (connectivity, create/delete project and AOI, cascade confirmation) in CI; passes locally and against the Compose stack.
- [x] *(follow-up)* Basemap default `none`; `osm` opt-in, development-only, refused in production builds; `xyz` explicit with attribution; invalid config warns and falls back.
- [x] *(follow-up)* CORS methods derived from declared operations; every operation passes a preflight in tests.
- [x] GitHub Actions run #7 (`02b6b05`) green on all six jobs including `e2e`.

## Phase 3 — Remote sensing connectors
> **Update 2026-10-06:** Phase 3a (fixtures-only) is ACCEPTED by the owner at `0c2406f` (CI run #21); the boxes below describe the whole of Phase 3 including live connectors and stay unticked; the matrix of what 3a verified (passed / simulated / policy-only) is `docs/phase-reports/phase-3a-closure.md`. Phase 3b onward is not started and not authorised; F-1 is not waived for live work.
> *Historical status note (2026-10-04):* Phase 3 is Planned — not started; ADR-0014 Accepted 2026-10-05 (not implemented); the fixtures-only Phase 3a scope accepted 2026-10-05 (scope acceptance only, not a start instruction); blocked pending a separate, explicit, bounded start instruction; D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved. The boxes below are not scheduled. D8 split (2026-10-05): the verification *strategy* is resolved (option D); live-verification *readiness* is pending its prerequisites; neither is acceptance of live connector functionality.

Detailed, extended criteria (13 items) and slice gates: `docs/phase-3-plan.md` §7 *(final plan, approved with constraints; Phase 3a accepted as fixtures-only 2026-10-06, later slices not started; supersedes this list when a live slice is started)*. Out-of-scope list: §0b; permitted operations: §0c. Summary of the original list:
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
