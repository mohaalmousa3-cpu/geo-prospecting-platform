# Phase 3 Plan — Remote-Sensing Data Connectors (PROPOSAL)

Status: **proposal for owner review. Nothing in this plan has been implemented or started.** Date: 2026-10-04.
Prerequisites met: Phases 1, 2, 2.5 accepted; the two Phase 2.5 follow-ups (browser smoke test in CI, `none` basemap default) are implemented.

## 0. What Phase 3 is, and is not

**Is:** getting *inputs* ready — finding which public imagery exists for an AOI and time window, staging a clipped elevation model, and accepting user-supplied vector layers — with budgets, caching, provenance and tests that never touch the network.

**Is not (hard exclusions, unchanged):** no thermal/LST, no band maths, no cloud masking, no indices, no prospectivity/void/anomaly logic, no scoring, no Earth Engine code (blocked, §6 slice 3e), no 3D, no authentication expansion. **Phase 5 remains blocked until the owner defines the target country/region and pilot area** (ADR-0003 amendment); Phase 3 therefore builds **no region-specific geology connector**. Phase 3 outputs are **data inputs, not scientific results**, and carry no confidence/score/interpretation.

Honesty rule for everything Phase 3 shows: values like scene-level cloud cover are *what the provider's metadata says*, labelled as such; they are not a statement about data quality over the AOI.

## 1. Key constraint discovered while planning (confidence: confirmed)

The cloud sandbox this project is built in **cannot reach the candidate EO providers**: read-only `GET`s to the Earth Search, Planetary Computer and Copernicus Data Space STAC `/collections` endpoints returned no response (connection blocked by the environment's network policy). Consequences:
1. Every provider statement in this plan (collection names, URL layouts, licences, rate limits) is **unverified**. They are listed as assumptions and each connector starts with a verification task.
2. Connectors are developed **fixture-first**: recorded/synthetic responses and synthetic rasters, no live calls in tests (already a project rule).
3. Real-world verification needs a machine with internet access: a read-only `make connectors-live-check` (a few tiny requests, prints a report, writes nothing to the database) which **the owner runs**, or the owner allowlists the provider hosts in the cloud environment's network settings so I can run it (decision D8). Until then, "works against the real provider" must not be claimed.

## 2. Inherited constraints (binding)
ADR-0004 (EE optional/replaceable/off, owner must validate commercial eligibility first) · ADR-0005 (no auth; loopback only) · ADR-0006 (local storage via `StorageBackend`) · ADR-0007 (Postgres queue; handlers idempotent, at-least-once) · ADR-0008 (limits are provisional safeguards; `MAX_SCENES_PER_JOB=20`, `MAX_TIME_WINDOW_DAYS=365`, 1800 s timeout) · ADR-0009/0010 (naming, envelope, no "confirmed") · ADR-0011 (`geo_common` holds no analysis logic) · ADR-0013 (projects, derived CORS, smoke test in CI) · `docs/data-model.md` (job↔project/AOI attachment, deletion rules) · `docs/job-lifecycle.md`.

## 3. Design

### 3.1 New package and entities (needs approval: ADR-0014, draft in `docs/adr/0014-connectors-package-and-data-assets.md`)
- **`workers/connectors/` (`geo_connectors`)** — connector implementations and their shared plumbing (budgeted HTTP client, cache, provenance). It imports `geo_common`; the backend does **not** import it (the backend validates requests and reads `data_asset` rows only); handlers are registered in `workers/runner` by import path. Connectors do data *access*, never interpretation.
- **Migration 0004** — `job.project_id` and `job.aoi_id` (nullable, FKs `ON DELETE RESTRICT`; `CHECK`: every non-`noop` job has both). `project_id` is **derived server-side from the AOI**, never client-supplied.
- **Migration 0005** — `data_asset(id, project_id, aoi_id, job_id NULL, kind, storage_key, media_type, size_bytes, sha256, provenance_id, created_at)`; `kind ∈ {scene_catalog, dem_clip, user_vector}`. A `data_asset` is an **input**; it is not a `result` and has no envelope fields.
- Deletion: deleting an AOI/project that has assets requires the explicit `delete_aois`-style flag and also removes the stored files; a project/AOI with a `queued`/`running` job cannot be deleted (409).

### 3.2 Connector contract (`geo_connectors.base`)
```
Connector.describe()  -> id, provider, version, licence + terms URL, attribution, requires_credentials,
                         sends_to_provider (human-readable: exactly what leaves the machine), rate limit
Connector.estimate(req) -> requests, max_bytes     # computed before any network access; checked against budgets
Connector.fetch(req, ctx) -> assets[], sources[] (envelope `Source` shape), insufficient_data_reason | None
ctx = FetchContext(http: BudgetedClient, cache, storage, clock)     # injected; tests substitute fakes
```
Outcomes: assets staged → job `succeeded`; nothing found for the AOI/window → job **`insufficient_data`** with an explanation (never silent defaults); budget exceeded / provider error after retries → `failed` with reason.

### 3.3 Safety, privacy, cost
- **Modes:** `CONNECTOR_MODE ∈ {disabled (default), fixture, live}`. `disabled` makes no outbound requests; `fixture` serves recorded responses (tests, demos, CI); `live` requires explicit opt-in plus `ENABLED_CONNECTORS=…`. EE is not a mode; it is a separate flag (ADR-0004).
- **SSRF/egress control:** request URLs are built only from a connector's fixed base URL and computed paths — never from user input; redirects and STAC `next` links are followed only to the same allow-listed host; responses are streamed with a hard size cap, content-type checked, JSON depth/size limited. Only the worker needs outbound access.
- **What leaves the machine** is shown to the user before a job is submitted (UI) and recorded in provenance: catalogue search sends the AOI bounding box/geometry and dates; DEM reads send tile identifiers and byte ranges (which still reveal the approximate area).
- **Budgets (provisional safeguards like ADR-0008; new env vars):** `CONNECTOR_TIMEOUT_SECONDS=30`, `CONNECTOR_MAX_RETRIES=3` (exponential backoff + jitter, honouring `Retry-After`), `CONNECTOR_MAX_REQUESTS_PER_JOB=50`, `CONNECTOR_MAX_RESPONSE_MB=20`, `MAX_DOWNLOAD_MB_PER_JOB=100`, `CONNECTOR_MAX_REQUESTS_PER_MINUTE=60`, `CATALOG_CACHE_TTL_HOURS=24`, `CACHE_MAX_MB=500`. Existing `MAX_SCENES_PER_JOB`, `MAX_TIME_WINDOW_DAYS`, `JOB_TIMEOUT_SECONDS` apply unchanged. No credentials anywhere in the repo.
- **Cache:** product-level, key = sha256(connector id+version, canonical request, bbox rounded to 1e-5°); stored under `cache/` via `StorageBackend`; size-capped with oldest-first eviction; a hit makes **zero** network calls and is recorded in provenance (`cache_hit`, original `retrieved_at`).
- **Provenance:** every asset links a `provenance` row: connector id/version, canonical request, provider host, retrieved_at, request/byte counts, sha256, licence + attribution text, software versions, and `Source` entries in the envelope shape (`dataset, version, acquired, licence, url, via`). `via ∈ {stac, direct, user_upload}` (`earth_engine` reserved).

### 3.4 What each connector produces
| Connector | Request | Output asset | Notes |
|---|---|---|---|
| `stac_catalog` | AOI, date window (≤ 365 d), collections allow-list, `max_items ≤ MAX_SCENES_PER_JOB` | `scene_catalog`: GeoJSON FeatureCollection of items (id, datetime, platform, collection, footprint, provider-reported scene cloud cover, **asset keys/links — nothing downloaded**) | Candidate collections (unverified): Sentinel-2 L2A, Landsat Collection 2 Level-2, Sentinel-1. Metadata only. |
| `dem_cop30` | AOI | `dem_clip`: clipped COG (+ nodata, CRS, resolution) | Candidate: Copernicus DEM GLO-30 COG tiles on AWS Open Data (unverified). Metadata must state it is a **surface model** (includes canopy/buildings) and its **vertical datum** (verify; believed EGM2008). AOI ≤ 25 km² ⇒ at most a few 1° tiles. |
| `user_vector` | uploaded GeoJSON / KML / KMZ / zipped Shapefile (region-agnostic geology, faults, occurrences) | `user_vector`: normalised GeoJSON in EPSG:4326 | Reuses Phase 2 archive/XML hardening; adds feature-count and attribute-size caps; provenance flagged `user_upload`. **This is the Phase 3 path for geology/occurrence data** until the region is defined. |

### 3.5 API and UI (minimal)
- `POST /api/v1/jobs` gains types `catalog_search` and `dem_fetch` (payload: `aoi_id` + parameters; validated by discriminated models; unknown fields rejected; AOI must exist). `Job` contract gains `project_id`, `aoi_id`.
- `GET /api/v1/connectors` (read-only: describe() output + whether enabled), `GET /api/v1/aois/{id}/assets`, `GET /api/v1/assets/{id}` (metadata + provenance), `GET /api/v1/assets/{id}/content` (size-capped, fixed media type, attachment), `POST /api/v1/aois/{id}/vector-layers` (upload), `DELETE /api/v1/assets/{id}`.
- CORS needs no edit (derived from operations, ADR-0013). Contracts in `packages/schemas`; generated types.
- UI: a **Data** panel for the selected AOI — connector choice, date window, "what will be sent to the provider" text, job status, results table (date, platform, collection, *provider-reported* scene cloud cover, link keys) or the explicit `insufficient_data` message; DEM/vector assets listed with size/provenance. No map overlay of scientific meaning; footprints may be drawn as outlines only.

### 3.6 Testing strategy
- **No live network in any test or CI job.** `httpx.MockTransport` + recorded/synthetic fixtures; synthetic COGs generated in-test with `rasterio`.
- Contract tests run against every connector (describe/estimate/fetch invariants, provenance completeness, budgets enforced, cache hit = zero requests).
- Hostile-response tests: oversize body, endless pagination, redirect to a non-allow-listed host, wrong content type, truncated/invalid JSON, deeply nested JSON, 429/5xx with and without `Retry-After`, slow responses.
- Idempotency/at-least-once: running a handler twice yields one logical asset (keyed by request hash) and consistent provenance.
- Browser smoke test (CI `e2e`) extended: worker added to the stack, `CONNECTOR_MODE=fixture`, flow = select AOI → run catalogue search → see results → delete asset; plus `insufficient_data` path. Guard tests: `disabled` default, no connector module imported by the backend, no EE import, no analysis vocabulary in connector outputs (extends the forbidden-term scan).
- Live verification only through the manual `connectors-live-check` (§1, D8).

## 4. Dependencies (to be approved, licences verified from package metadata at install)
`httpx` (BSD-3; already a dev dependency → becomes runtime for the worker) · `rasterio` (BSD-3; wheels bundle GDAL — larger image, to be measured) · `numpy` (already present). **No `pystac-client`**: the STAC search surface we need is small; a minimal `httpx` client keeps SSRF/budget control and avoids a second HTTP stack. All connector dependencies live in `geo_connectors`, not in `geo_common`. No copyleft expected; the licence check script gates it.
Open technical spike (P3-14): DEM reads must pass through our budgeted client. Preferred: `rasterio.open(..., opener=…)` with a ranged-read adapter over `httpx` (believed supported in recent rasterio — verify); fallback: GDAL `/vsicurl` with strict `GDAL_HTTP_*` limits, accepting weaker byte accounting.

## 5. Risks (added to the risk register on approval)
Provider API drift or outages · unverified provider terms/rate limits · licence/attribution obligations for derived DEM clips · large downloads exceeding budgets · GDAL/rasterio footprint and install fragility · scene-level cloud cover being mistaken for AOI-level quality · a DEM *surface* model being mistaken for terrain · AOI location leaking via tile/byte-range requests · cache poisoning or stale catalogue results · sandbox cannot verify live behaviour (§1).

## 6. Slices, tasks and review gates

Each slice ends with: `make ci-full` green locally, GitHub Actions green (including `e2e`), a short report, and **owner review before the next slice**.

### 3a — Foundations (no provider code)
| ID | Task | Done when |
|---|---|---|
| P3-01 | ADR-0014 accepted (package, `data_asset`, job linkage, modes) | owner approval recorded |
| P3-02 | Migration 0004 (`job.project_id/aoi_id`, CHECK) + migration test incl. existing `noop` jobs | up/down/up passes; noop unaffected |
| P3-03 | Jobs API: `catalog_search`/`dem_fetch` payload models, AOI lookup, derived project, queue-full & limits unchanged; deletion blocked while a job is queued/running | API + integration tests |
| P3-04 | Settings + `.env.example` for modes and budgets (defaults `disabled`); config-drift test updated | tests pass |
| P3-05 | `geo_connectors` skeleton: `Connector` ABC, registry, `BudgetedClient` (timeouts, retries/backoff, rate limit, size caps, same-host redirects), `FetchContext` | unit tests incl. every hostile-response case above |
| P3-06 | Cache (key, TTL, size cap, eviction) and provenance helper | cache-hit-makes-zero-requests test; provenance completeness test |
| P3-07 | Migration 0005 `data_asset` + repository + asset endpoints (list/get/content/delete) + deletion rules | API tests; file removed with asset; path-traversal tests |
| P3-08 | Fixture harness (`CONNECTOR_MODE=fixture`) and connector contract test suite | suite runs against a fake connector |
| P3-09 | Docs: `docs/connectors.md`, data-model + job-lifecycle updates | reviewed |

### 3b — STAC catalogue search
| P3-10 | Verify assumptions: write `connectors-live-check` (read-only, tiny) | script exists; **owner runs it** (D8) |
| P3-11 | `stac_catalog` connector (fixtures from the live-check output once available; synthetic until then) | contract suite + pagination/limits/dates tests; zero results → `insufficient_data` |
| P3-12 | `catalog_search` handler in the runner; idempotent asset keyed by request hash | at-least-once test |
| P3-13 | UI Data panel (catalogue only) + e2e extension (worker in CI, fixture mode) | `make e2e` passes incl. `insufficient_data` path |

### 3c — DEM
| P3-14 | Spike: ranged-read adapter vs `/vsicurl` (budget accounting) → short note | decision recorded |
| P3-15 | `dem_cop30` connector: tile selection, windowed read, clip, COG write, metadata (datum, surface-model caveat, resolution, attribution) | synthetic-COG tests incl. multi-tile AOI, nodata, AOI at tile edge |
| P3-16 | `dem_fetch` handler + UI row + e2e step | asset listed with provenance |

### 3d — User-supplied vector layers
| P3-17 | Upload endpoint + parsers reuse (GeoJSON/KML/KMZ/Shapefile), feature/attribute/size caps, CRS handling, bbox filter | hostile-input tests (reuse Phase 2 set + feature bombs) |
| P3-18 | UI upload in Data panel; asset listing | e2e step |

### 3e — Earth Engine (**BLOCKED**)
| P3-19 | Starts only after the owner records, in writing, that the account's use is eligible (ADR-0004 amendment). Then: connector behind `ENABLE_EARTH_ENGINE`, lazy import, fixtures only in tests, `via: earth_engine` provenance, non-EE path remains | owner unblock recorded; otherwise this slice is skipped without affecting Phase 3 acceptance |

### 3f — Closeout
| P3-20 | `docs/phase-reports/phase-3.md`, acceptance checklist, risk register, third-party licence register, README/TASKS | owner acceptance |

## 7. Acceptance criteria (Phase 3)
1. `CONNECTOR_MODE` defaults to `disabled`; with it, no connector makes any outbound request (tested). `live` needs explicit opt-in; EE needs its own flag and is absent unless unblocked.
2. Every connector implements the contract; budgets (requests, bytes, time, items, window) are enforced and tested at, below and above the limit.
3. A cache hit performs zero network calls; stale catalogue entries expire by TTL; the cache size cap evicts.
4. Every asset has a provenance record with licence, attribution, request, host, counts, checksum; `Source` entries match the envelope schema.
5. Empty results yield `insufficient_data` with an explanation; provider errors yield `failed` with a reason; no silent defaults.
6. Hostile responses and files (list in §3.6) are rejected without crashing the worker or leaking paths.
7. Job↔project/AOI linkage and deletion rules (§3.1) are enforced and tested; running jobs block deletion.
8. UI shows what is sent to the provider before submission, labels provider-reported values as such, and shows no analysis.
9. The browser smoke test (CI `e2e`) covers the catalogue flow in fixture mode; no CI job touches the network except package/browser installation.
10. No connector, output or UI string contains analysis/scoring vocabulary (forbidden-term scan extended); backend does not import `geo_connectors`.
11. Live behaviour is either verified by the owner's `connectors-live-check` report (attached to the phase report) or explicitly reported as **unverified**.

## 8. Decisions requested from the owner
| # | Decision | My recommendation |
|---|---|---|
| D1 | Approve the slice order and review gates (3a→3b→3c→3d, 3e blocked) | Approve |
| D2 | Approve ADR-0014: `workers/connectors` package, `data_asset` entity, job↔project/AOI columns | Approve |
| D3 | Approve `rasterio` (BSD-3, bundles GDAL) as a worker dependency | Approve after measuring image size in 3a |
| D4 | Default catalogue provider | Earth Search first (open search, no credentials — **unverified**); provider id stays configurable; Planetary Computer / CDSE as later alternates |
| D5 | DEM source | Copernicus DEM GLO-30 (COG, AWS Open Data — **unverified**, licence/attribution to confirm) |
| D6 | `CONNECTOR_MODE` default `disabled`, `live` opt-in | Approve |
| D7 | Budget defaults in §3.3 | Approve as provisional safeguards (not measured) |
| D8 | Live verification: owner runs `make connectors-live-check` on an internet-connected machine, **or** allowlists the provider hosts in the cloud environment so I can | Either; without one of them Phase 3 is accepted as "fixture-verified, live-unverified" |
| D9 | Earth Engine stays blocked until your written eligibility validation | Keep blocked |
| D10 | Geology/occurrence data in Phase 3 = user-supplied vector layers only; national-survey connectors wait for the Phase 5 region decision | Approve |
| D11 | CI `e2e` grows a worker process and fixture mode | Approve |
| D12 | Phase 5 region/pilot-area gate and "no analysis" rule unchanged | Confirm |

## 9. Explicitly out of scope (restated)
Band downloads for analysis, cloud masking, LST, indices, any scoring, EE code before unblock, 3D, auth, region-specific geology connectors, automatic AOI tiling, retention/purge of assets (tracked as deferred), multi-worker concurrency.
