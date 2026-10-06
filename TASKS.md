# TASKS.md — Phased Implementation Roadmap

Legend: `[ ]` todo · `[x]` done and verified · Only the **current phase** may be worked on (see `CLAUDE.md`).
Acceptance criteria per phase: `docs/acceptance-criteria.md`.

**Current status (2026-10-05; authoritative source: `MASTER_SPEC.md` → Current Project Status).** Phases 0–2.5 are *implemented*; the owner's decisions D-1…D-6 of 2026-10-05 are recorded (transcribed in `docs/phase-reports/acceptance-reconciliation.md` §2) and only the boxes they support were ticked. **Phase 3: **Update 2026-10-05 (owner start instruction): Phase 3a (fixtures-only) is authorised checkpoint by checkpoint — CP1 (connector skeleton), CP2 (migration 0004, AOI-bound enqueue, r5 deletion rewrite) and CP3 (migration 0005, assets, publication protocol, results guard, tombstones) — CP2 and CP3 accepted by the owner as completed checkpoints (CP3 at `0f0b967`, CI #17) — and CP4 (authorised 2026-10-06: fixtures-only `catalog_search` job creation through the API, worker-image packaging, end-to-end fixture execution, T3/T4/T9–T11 work, `docs/connectors.md`, the `ON DELETE CASCADE` decision note; **accepted by the owner as a completed checkpoint at `f3243a9`, CI #20**), and a final bounded closure checkpoint (authorised 2026-10-06: migration 0006, compose fixes, `GET /connectors`, `GET /aois/{id}/assets`, provenance helper, reconciliation and the T1–T11 matrix in `docs/phase-reports/phase-3a-closure.md`; **implemented and awaiting the owner's review, not accepted**) on branch `claude/phase-3a-fixtures`, base `6b8d15e` — Phase 3a as a whole is **not complete and not accepted**; slices 3b onward not started; each checkpoint stops for the owner's review.** Earlier status, kept as history: planned; ADR-0014 Accepted 2026-10-05 (r5 deletion amendment accepted; implemented only as far as the first checkpoint's connector skeleton); the fixtures-only Phase 3a scope accepted as scope; a separate bounded start instruction was required (now given for the first checkpoint); D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved.** ADR-0014 was explicitly **Accepted** by the owner on 2026-10-05 (not implemented; acceptance is not a start instruction). D8: the verification **strategy** was resolved on 2026-10-05 (option D), live-verification **readiness** is pending. ADRs are 0001…0014 (0014 Accepted, not implemented). Not started and not allowed yet: Earth Engine, thermal/gold/void scoring, remote-sensing analysis, 3D rendering, any scientific inference layer.

> *Historical banner (superseded; as written at the Phase 3 plan proposal):* "Current phase: 2.5 follow-ups done; Phase 3 PLAN proposed (`docs/phase-3-plan.md`), implementation not started and awaiting owner approval. Owner decisions are recorded as ADRs (`docs/adr/`, 0001…0012)."

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

> Status note (2026-10-04): the items above are recorded as done; the Phase 0 boxes in `docs/acceptance-criteria.md` are unticked and need a reconciliation decision (see the dated note there). **Update 2026-10-05 (D-2):** the owner accepted Phase 0 within its historical planning/scaffolding scope; this does not show that today's documents are free of contradictions. **Follow-up (2026-10-05, owner):** the acceptance-criteria item *all files exist and are internally consistent* stays open as a documented follow-up (F-1: documentation consistency). It is not claimed complete; whether it blocks a Phase 3 start under the phase-start rules is identified in `MASTER_SPEC.md` (Current Project Status) for the owner to resolve before any start instruction. **Owner exception (2026-10-05):** F-1 is designated a non-blocking documentation follow-up for the fixtures-only Phase 3a slice only (narrow exception; not a change to the phase-start rules; not a declaration that F-1 is satisfied); it must be closed before any live connector slice is authorised; known issues: `docs/phase-reports/acceptance-reconciliation.md` §9a. This does not authorise Phase 3a to start.

## Phase 1 — Repo/App Foundation
Implemented 2026-10-04; evidence and deviations in `docs/phase-reports/phase-1.md`. *[historical, superseded by the status note below]* **Awaiting owner acceptance** before Phase 2. Detailed, ordered tasks with verification commands: **`docs/phase-1-plan.md`** (P1-01 … P1-18). Summary:
- [x] Tooling baseline (lint, type-check, tests, secret scan, forbidden-term scan)
- [x] CI workflow executed green on GitHub Actions (written; passes locally via `make ci`)
- [x] Docker Compose: postgis, backend, worker, frontend — loopback ports, no Redis, no MinIO
- [x] FastAPI skeleton: `/health`, config, logging, `/api/v1`
- [x] Alembic + PostGIS; tables `aoi`, `job`, `result`, `provenance`
- [x] `StorageBackend` (local) and `JobQueue` (PostgreSQL) interfaces with tests
- [x] Worker with claim/lease/heartbeat/timeout/cancel and a no-op job
- [x] Schemas → Pydantic/TS generation; result envelope incl. `validation_status`, `calibration_status`, `engine_status`
- [x] Next.js skeleton + status page
- [x] Scientific-guard tests; `docs/third-party-licences.md`
- [x] `LICENSE` stays rights-reserved placeholder (ADR-0002)

> Status note (2026-10-04): the *Awaiting owner acceptance* sentence above is historical. Owner acceptance **with follow-up checks** is recorded in `docs/phase-reports/phase-1-closeout.md`. Verification evidence for the unticked CI box: GitHub Actions run #3 on `bbab3c8` concluded `success` (python, frontend incl. schema drift, gitleaks, dependency audit [report-only], docker build); runs #1 (`823fa87`) and #2 (`eda2681`) failed. The box stays unticked pending a reconciliation decision. **Update 2026-10-05 (D-3):** the owner accepted the reported evidence (CI run #3 and later; clean-checkout Compose run for `5ac5a27`) for the three open acceptance-criteria items and for this CI box; the box is now ticked.

## Phase 2 — AOI Input and Map Basics
Implemented 2026-10-04 (plan: `docs/phase-2-plan.md`, ADR-0012, evidence: `docs/phase-reports/phase-2.md`). *[historical, superseded by the status note below]* **Awaiting owner acceptance.** Still no analysis of any kind.
- [x] GitHub Actions run green on the tip commits of the Phase 2 pushes: runs #4 (`2ddef67`) and #5 (`1e7c823`) concluded `success`. **Verified from Git (2026-10-05, `git merge-base --is-ancestor`):** `46596b4` is the direct parent of `2ddef67` (the only commit between them) and an ancestor of `1e7c823`, so the tree tested by run #4 contains `46596b4`'s changes. This is **not** an independent CI run for `46596b4`, and no intermediate snapshot was tested separately. *Wording clarified 2026-10-05; original: "GitHub Actions run green on the Phase 2 commits (check after push)" — read literally as "a run for every Phase 2 commit" it would NOT be satisfied.*
- [x] AOI model + API: preview/create/upload/list/get/delete/limits
- [x] Coordinates + radius → polygon (geodesically correct)
- [x] Geometry validation, CRS normalisation (EPSG:4326 + working UTM), area limits. *Simplification not done: over-limit inputs are rejected, not simplified.*
- [x] Upload parsers: GeoJSON, KML, KMZ, zipped Shapefile (in-memory, hardened)
- [x] MapLibre 2D map: base map, draw rectangle/polygon/centre, display saved & uploaded AOI. *Vertex editing deferred (redraw instead, ADR-0012).*
- [x] Coordinate/radius input form (and rectangle/polygon numeric forms)
- [x] AOI persistence and reload
- [x] Tests: malformed/hostile uploads, antimeridian, self-intersections, huge AOIs

> Status note (2026-10-04): the *Awaiting owner acceptance* sentence above is historical. Owner approval **with follow-up items** is recorded in `docs/phase-reports/phase-2.md`. Verification evidence for the unticked CI box: runs #4 (`2ddef67`) and #5 (`1e7c823`) concluded `success`; commit `46596b4` has no run of its own. The box stays unticked pending a reconciliation decision. The Phase 2 UI delete claim was amended by the Phase 2.5 CORS finding (`phase-2.5.md` §2). **Update 2026-10-05 (D-4):** the owner accepted the upload/archive boundary-test gap as closed (evidence: CI run #11 on `5ac5a27`). D-4 does not mention this CI box, so it **stays open**: evidence exists (runs #4, #5) but no explicit decision covers it. **Update 2026-10-05 (owner, second message):** the owner approved ticking this box on the evidence of runs #4 and #5, on condition that the box does not imply a run that does not exist. The box wording was therefore clarified (see the item above; the original wording is preserved in it) and ticked. It does **not** claim an independent run for `46596b4`. **Update 2026-10-05 (owner, third message):** the owner approved the clarified wording and the checked item, conditional on the ancestry claim being verified from Git; it was verified (see the item). The distinction between "the tested tip contains earlier changes" and "each earlier commit had an independent CI run" is preserved.

## Phase 2.5 — Structural Hardening (owner-approved insert before Phase 3)
Implemented 2026-10-04 (ADR-0013, `docs/data-model.md`, report + acceptance checklist: `docs/phase-reports/phase-2.5.md`). *[historical, superseded by the status note below]* **Awaiting owner acceptance; Phase 3 must not start before it.**
- [x] Minimal `project` entity; AOIs belong to projects; migration `0003`
- [x] Backend contracts, persistence, API (`/projects`, `project_id` on AOIs)
- [x] Smallest project-aware frontend flow
- [x] Basemap provider abstraction (`osm` | `xyz` | `none`)
- [x] Document project ↔ AOI ↔ future jobs ↔ outputs
- [x] Fix: CORS now allows `DELETE` (found by browser check; affected Phase 2 UI deletes)
- [x] Follow-up 1: browser smoke test in CI (`e2e` job, `make e2e`)
- [x] Follow-up 2: default basemap `none`; `osm` opt-in/dev-only; `xyz` explicit
- [x] Extra: CORS methods derived from declared operations
- [x] GitHub Actions green incl. the new `e2e` job (run #7, `02b6b05`)

> Status note (2026-10-04): conditional owner approval is recorded (two required follow-ups). The follow-ups are *reported implemented and tested*; run #7 on `02b6b05` is **historical evidence**; run #10 on `da90ce2` (current committed HEAD, documentation-only delta from #7) concluded `success` on six jobs incl. `e2e`. A **separate owner sign-off on the follow-ups is not recorded**; approval of the Phase 3 plan is not that sign-off. The *"Phase 3 must not start before it"* constraint above remains in force. **Update 2026-10-05 (D-1):** the owner accepted the two follow-ups and the derived-CORS addition within their documented scope, closing the Phase 2.5 acceptance gate (not a claim of exhaustive UI-interaction or runtime-text coverage). Approval of the Phase 3 plan was never that acceptance.

## Phase 3 — Remote Sensing Connectors
**FINAL PLAN (Phase 3a first checkpoint in progress since 2026-10-05; all other slices not started): `docs/phase-3-plan.md` (scope summary, strict out-of-scope §0b, permitted operations §0c, slices 3a–3f, tasks P3-01…P3-20, decision table D1–D12). The owner approved the plan with constraints; ADR-0014 was **Accepted** on 2026-10-05 (not implemented) and the fixtures-only Phase 3a scope was accepted as scope; implementation needs a separate, explicit, bounded start instruction per checkpoint (given 2026-10-05 for the first Phase 3a checkpoint only). D8: strategy resolved 2026-10-05 (Phase 3a fixtures-only; live verification mandatory before accepting live slices 3b and DEM; route B preferred subject to separate approval of the exact host allowlist, otherwise route A) — live-verification readiness is pending and no host is approved. Earth Search and Copernicus GLO-30 are TENTATIVE defaults.** Phase 3 stages data inputs only — no scoring, prospectivity inference, thermal analysis, Earth Engine execution, 3D or scientific interpretation. Phase 5 region gate unchanged.

> Status note (2026-10-04): **Update 2026-10-05 (owner start instruction): Phase 3a (fixtures-only) is authorised checkpoint by checkpoint — CP1 (connector skeleton), CP2 (migration 0004, AOI-bound enqueue, r5 deletion rewrite) and CP3 (migration 0005, assets, publication protocol, results guard, tombstones) — CP2 and CP3 accepted by the owner as completed checkpoints (CP3 at `0f0b967`, CI #17) — and CP4 (authorised 2026-10-06: fixtures-only `catalog_search` job creation through the API, worker-image packaging, end-to-end fixture execution, T3/T4/T9–T11 work, `docs/connectors.md`, the `ON DELETE CASCADE` decision note; **accepted by the owner as a completed checkpoint at `f3243a9`, CI #20**), and a final bounded closure checkpoint (authorised 2026-10-06: migration 0006, compose fixes, `GET /connectors`, `GET /aois/{id}/assets`, provenance helper, reconciliation and the T1–T11 matrix in `docs/phase-reports/phase-3a-closure.md`; **implemented and awaiting the owner's review, not accepted**) on branch `claude/phase-3a-fixtures`, base `6b8d15e` — Phase 3a as a whole is **not complete and not accepted**; slices 3b onward not started; each checkpoint stops for the owner's review.** Earlier status, kept as history: planned; ADR-0014 Accepted 2026-10-05 (r5 deletion amendment accepted; implemented only as far as the first checkpoint's connector skeleton); the fixtures-only Phase 3a scope accepted as scope; a separate bounded start instruction was required (now given for the first checkpoint); D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved. Approval of the plan is not authorization to start implementation. The boxes below are not scheduled until the block is lifted.
> Phase 3a evidence note (2026-10-06): the boxes below describe the whole of Phase 3, live connectors included, so **none is ticked**. What the fixtures-only slice has implemented and verified, checkpoint by checkpoint and labelled real / simulated / policy-only, is in `docs/phase-3-plan.md` (CP2–CP4 status and the T-case ledger) and `docs/connectors.md`. Phase 3a is **not complete and not accepted**.
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
