# Phase 3 Plan — Remote-Sensing Data Connectors (FINAL PLAN — NOT STARTED, BLOCKED)

Status: **planning finalised after the owner's "approved with constraints" (2026-10-04). Nothing in this plan has been implemented or started. Implementation needs a separate, explicit, bounded start instruction.** ADR-0014 was explicitly **Accepted** by the owner on 2026-10-05 (not implemented).
**Current status (2026-10-04): Planned — not started; ADR-0014 Accepted 2026-10-05 (not implemented); the fixtures-only Phase 3a scope accepted 2026-10-05 (scope acceptance only, not a start instruction); blocked pending a separate, explicit, bounded start instruction; D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved.** Approval of this plan is not authorization to start implementation.
Prerequisite status (updated 2026-10-05; authoritative source: `MASTER_SPEC.md` → Current Project Status): the owner's decisions D-1…D-4 of 2026-10-05 record acceptance of the Phase 2.5 follow-ups and the derived-CORS addition, of Phase 0 within its historical scope, of the Phase 1 open checks, and of the Phase 2 upload/archive boundary-test gap; the `TASKS.md` Phase 2 "Actions green" item was ticked on 2026-10-05 with clarified wording (runs #4/#5; no independent run for `46596b4`); Phase 0's documentation-consistency item stays open as follow-up F-1, and by the owner's narrow exception of 2026-10-05 it is non-blocking for the fixtures-only Phase 3a slice only and must be closed before any live connector slice is authorised (see `MASTER_SPEC.md`). *Historical wording (2026-10-04), superseded:* "a separate owner sign-off on those follow-ups is not recorded; acceptance reconciliation is pending." Acceptance of earlier phases is not authorization to start Phase 3.
*Historical wording, superseded:* "Prerequisites met: Phases 1, 2, 2.5 accepted" — written before the acceptance records were reconciled; it overstated the Phase 2.5 record.

## Scope summary (one page, for review)

| Item | Final Phase 3 scope |
|---|---|
| Purpose | Stage **data inputs** for later phases: *ingest → normalise (format only) → clip → validate → store*, with provenance. Nothing is interpreted. |
| Connectors | (1) `stac_catalog` — metadata search of public imagery catalogues; (2) `dem_cop30` — clipped elevation raster; (3) `user_vector` — user-supplied geology/fault/occurrence vector files. |
| Tentative defaults | Catalogue: **Earth Search**; DEM: **Copernicus DEM GLO-30**. Both **TENTATIVE, unverified** (the build sandbox cannot reach providers); they become defaults only after live verification (D4, D5, D8; see §8a). |
| Outputs | `data_asset` rows + files: `scene_catalog` (JSON), `dem_clip` (COG), `user_vector` (GeoJSON), each with a provenance record. They are inputs, **not results**; no confidence/score fields. |
| Safety | `CONNECTOR_MODE=disabled` by default; `fixture` for tests/CI; `live` explicit opt-in. Budgets on requests, bytes, time, items, window. Same-host-only egress. Cache with TTL and size cap. |
| Tests | Fixture-first, **no live network in tests or CI**; hostile-response tests; extended browser smoke test (fixture mode) in CI. |
| Slices & gates | 3a foundations → 3b STAC → 3c DEM → 3d user vectors → 3f closeout; **3e Earth Engine blocked** (not executed, not implemented). Owner review after each slice. |
| Needs from the owner before code | Explicit start approval (Phase 3a only is intended); ADR-0014 Accepted 2026-10-05 (not implemented); D8 strategy is resolved (§8a) — live-verification readiness is needed before accepting live slices. |
| Unchanged | Phase 5 gate (target region + pilot area), ADR-0003/0004/0005/0008/0009/0010/0011/0013. |

## 0. What Phase 3 is

**Is:** getting *inputs* ready — finding which public imagery exists for an AOI and time window, staging a clipped elevation model, and accepting user-supplied vector layers — with budgets, caching, provenance and tests that never touch the network.

**Is not:** everything in §0b (strict out-of-scope list). §0c lists the only data operations allowed.

Honesty rule for everything Phase 3 shows: values like scene-level cloud cover are *what the provider's metadata says*, labelled as such; they are not a statement about data quality over the AOI.

## 0b. OUT OF SCOPE — strict (canonical list)

Phase 3 **must not** contain, and its tests/guards must keep out:

1. **No scoring** of any kind (no `*_score`, ranking, weighting, thresholds on data values).
2. **No prospectivity inference** (gold, orogenic or otherwise) and no void/cavity evidence logic.
3. **No thermal analysis** (no LST retrieval, no thermal bands, no anomaly detection, no temperature products).
4. **No Earth Engine execution** — no EE import, no EE credentials, no EE calls, no EE code path enabled. Slice 3e stays blocked (ADR-0004 amendment: owner's written eligibility validation first), and even after unblocking it is a separate approval.
5. **No 3D** — no Cesium, no terrain rendering, no depth of any kind.
6. **No scientific interpretation beyond data ingestion, normalisation, clipping, validation and storage** (see §0c for the exact meaning of each). In particular: no band maths or indices, no cloud/shadow masking, no resampling or interpolation of pixel values, no derived terrain products (slope, aspect, curvature), no statistics beyond file/metadata bookkeeping (counts, sizes, checksums), no quality judgement about the data over the AOI.
7. No region-specific geology connectors (waits for the Phase 5 region decision), no authentication expansion, no automatic AOI tiling, no multi-worker concurrency, no retention/purge, no band downloads for later analysis.
8. No claim that a connector "works with provider X" before live verification (§1).

Enforcement (becomes acceptance criteria 12–13 in §7): import allow-list tests for `geo_connectors` and `apps/backend` (no analysis/ML/EE libraries), output-schema allow-list (unknown keys rejected), forbidden-vocabulary scan extended to connector outputs and UI strings, `CONNECTOR_MODE=disabled` default test, and no `ENABLE_EARTH_ENGINE` code path reachable.

## 0c. Permitted data operations (exhaustive)

| Operation | Allowed meaning in Phase 3 | Not allowed |
|---|---|---|
| **Ingestion** | Fetching provider metadata/tiles within budgets; accepting user uploads | Anything beyond what the request needs |
| **Normalisation** (structure/format only) | STAC item → fixed JSON schema; datetimes → UTC ISO-8601; vector CRS → EPSG:4326; ring orientation; COG tiling/compression | Changing pixel/attribute **values**: radiometric or unit conversion, resampling, reprojection of rasters, smoothing, gap-filling |
| **Clipping** | Window/bbox read of the raster covering the AOI (native grid, no resampling), optional nodata mask outside the AOI polygon; vector bbox filter | Interpolation, mosaicking that blends values |
| **Validation** | Geometry/schema/size/type/checksum checks; hostile-input rejection | Judging scientific quality or usefulness |
| **Storage** | `StorageBackend` files + `data_asset`/`provenance` rows | Serving anything labelled as a finding |

Provider-reported fields (e.g. scene-level cloud cover) are **passed through unchanged and labelled as provider-reported**; they say nothing about clarity over the AOI.

## 1. Key constraint discovered while planning (confidence: confirmed)

The cloud sandbox this project is built in **cannot reach the candidate EO providers**: read-only `GET`s to the Earth Search, Planetary Computer and Copernicus Data Space STAC `/collections` endpoints returned no response (connection blocked by the environment's network policy). Consequences:
1. Every provider statement in this plan (collection names, URL layouts, licences, rate limits) is **unverified**. They are listed as assumptions and each connector starts with a verification task.
2. Connectors are developed **fixture-first**: recorded/synthetic responses and synthetic rasters, no live calls in tests (already a project rule).
3. **Tentative defaults.** Earth Search (catalogue) and Copernicus DEM GLO-30 (DEM) are **tentative defaults pending live verification**: they may be named in documentation and in fixtures-based code paths, but a provider is not enabled by default, advertised as working, or hard-coded as the only option until (a) `connectors-live-check` shows its endpoints, collections, URL layout, licence/attribution text and rate behaviour match this plan, and (b) the owner confirms. If verification fails, the connector falls back to the alternates (Planetary Computer / Copernicus Data Space for catalogues; an alternate open DEM) via a new ADR-sized decision, not a silent switch.
4. Real-world verification needs a machine with internet access: a read-only `make connectors-live-check` (a few tiny requests, prints a report, writes nothing to the database) which **the owner runs**, or the owner allowlists the provider hosts in the cloud environment's network settings so I can run it (decision D8: strategy resolved 2026-10-05, see §8a). Until a live-verification report exists, "works against the real provider" must not be claimed.

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
Outcomes: assets staged → job `succeeded`; nothing found for the AOI/window → job **`insufficient_data`** (queue terminal status, `docs/architecture.md` §4) with an explanation — an ingestion status only: no `result` row, no `data_asset`, no confidence or interpretation (never silent defaults); budget exceeded / provider error after retries → `failed` with reason.

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
| `stac_catalog` | AOI, date window (≤ 365 d), collections allow-list, `max_items ≤ MAX_SCENES_PER_JOB` | `scene_catalog`: GeoJSON FeatureCollection of items (id, datetime, platform, collection, footprint, provider-reported scene cloud cover, **asset keys/links — nothing downloaded**) | **Tentative default provider: Earth Search (unverified).** Candidate collections (unverified): Sentinel-2 L2A, Landsat Collection 2 Level-2, Sentinel-1. Metadata only. |
| `dem_cop30` | AOI | `dem_clip`: clipped COG (+ nodata, CRS, resolution), native grid, no resampling | **Tentative default source: Copernicus DEM GLO-30** COG tiles on AWS Open Data (unverified). Metadata must state it is a **surface model** (includes canopy/buildings) and its **vertical datum** (verify; believed EGM2008). AOI ≤ 25 km² ⇒ at most a few 1° tiles. |
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
- Live verification only through the read-only check defined in §8a (route B under an owner-approved allowlist, otherwise route A) (§1, D8).

## 4. Dependencies (to be approved, licences verified from package metadata at install)
`httpx` (BSD-3; already a dev dependency → becomes runtime for the worker) · `rasterio` (BSD-3; wheels bundle GDAL — larger image, to be measured) · `numpy` (already present). **No `pystac-client`**: the STAC search surface we need is small; a minimal `httpx` client keeps SSRF/budget control and avoids a second HTTP stack. All connector dependencies live in `geo_connectors`, not in `geo_common`. No copyleft expected; the licence check script gates it.
Open technical spike (P3-14): DEM reads must pass through our budgeted client. Preferred: `rasterio.open(..., opener=…)` with a ranged-read adapter over `httpx` (believed supported in recent rasterio — verify); fallback: GDAL `/vsicurl` with strict `GDAL_HTTP_*` limits, accepting weaker byte accounting.

## 5. Risks (added to the risk register on approval)
Provider API drift or outages · unverified provider terms/rate limits · licence/attribution obligations for derived DEM clips · large downloads exceeding budgets · GDAL/rasterio footprint and install fragility · scene-level cloud cover being mistaken for AOI-level quality · a DEM *surface* model being mistaken for terrain · AOI location leaking via tile/byte-range requests · cache poisoning or stale catalogue results · sandbox cannot verify live behaviour (§1).

## 6. Slices, tasks and review gates

Each slice ends with: `make ci-full` green locally, GitHub Actions green (including `e2e`), a short report, and **owner review before the next slice**.

### 3a — Foundations (fixtures-only; proposed exact scope, **not started, not authorised**)
Scope **accepted by the owner on 2026-10-05 as scope — not a start instruction** (with the clarifications of ADR-0014 r4 and the tests below). 3a adds **no** HTTP client, **no** `rasterio`, **no** live network code and **no** provider configuration (no provider URLs, hosts or budgets). The live-facing parts of the earlier 3a list moved to 3b (below). Boundary table: `docs/adr/0014-…` §11.

| ID | Task | Done when |
|---|---|---|
| P3-01 | ADR-0014 **Accepted** by the owner | **done 2026-10-05** (owner decision recorded) |
| P3-02 | Migration 0004 per ADR §7.1–§7.3: `aoi UNIQUE(id, project_id)`; `job.aoi_id/project_id`, composite FK, both-or-neither and non-`noop` CHECKs; abort-on-non-`noop` backfill rule | tests T1, T2 |
| P3-03 | Jobs API: job type `catalog_search` only; project derived from the AOI; `disabled` → explicit "connectors disabled"; `live` → explicit "not available"; deletion rules and lock order per ADR §7.4–§7.6 | tests T3, T7 |
| P3-04 | Settings: `CONNECTOR_MODE` only (`disabled` default, `fixture`), `.env.example`, config-drift test | tests pass |
| P3-05a | `geo_connectors` skeleton: `Connector` ABC, registry, `FetchContext`, **fixture connector** over committed synthetic fixtures; **no HTTP client, no cache** | tests T4, T5, T8 |
| P3-06a | Provenance helper | provenance-completeness test |
| P3-07 | Migration 0005 `data_asset` (+`storage_tombstone`), repository, asset endpoints (list/get/content/delete), cascade deletion with tombstones, drain, `make reconcile-assets` (drain + report only; no destructive orphan cleanup) | tests T6, T7 |
| P3-08 | Fixture harness and connector contract tests | tests T4 |
| P3-09 | Docs: `docs/connectors.md`, data-model + job-lifecycle updates | reviewed |

**3a acceptance tests (all offline; none exists yet):**
- **T1** migration 0004: up/down/up on an empty table; with `noop` rows only; with a seeded non-`noop` row (aborts atomically, lists ids); constraints present by introspection.
- **T2** database integrity (direct SQL): job with a `project_id` that differs from its AOI's fails; half-NULL pair fails; non-`noop` job without AOI fails; `noop` with NULLs succeeds; asset with NULL `project_id`/`aoi_id` fails; asset whose `job_id` belongs to another AOI/project fails; asset with `job_id` NULL succeeds; changing `aoi.project_id` while referenced fails; the same change on an unreferenced AOI is *not* blocked by the database (documents the actual protection).
- **T3** API: client-supplied `project_id` for a job is rejected; unknown AOI → 404; queue limits unchanged; `disabled` and `live` behave as specified.
- **T4** fixture connector end to end: job → handler → `scene_catalog` asset + provenance (all required fields) from a synthetic committed fixture; re-run does not duplicate the asset. **Zero results (clarified 2026-10-05):** the job ends in the **existing queue terminal status `insufficient_data`** (`JobStatus`, job-lifecycle contract in `docs/architecture.md` §4: "a normal terminal state with an explanation"; handler result `HandlerResult("insufficient_data", reason)`). In this context it means only **"the catalogue search completed and matched no items for the request"** — an ingestion/queue status, **not a scientific result**. It writes **no `result` row, no envelope, no `data_asset`**, and carries **no confidence, score or interpretation**; the explanation text (e.g. "no catalogue items matched the request") is stored in the job's `error` field as for any explained terminal status, and the UI/API wording says "no catalogue items matched". Test: empty fixture → status `insufficient_data` + explanation, and `result`/`data_asset` row counts unchanged. The same status name used by future analysis engines (CLAUDE.md §4.9) is a separate concept and is not implied here.
- **T5** no external network from the connector (clarified 2026-10-05): the guard is **scoped to connector execution** and does not forbid the worker's or the test infrastructure's PostgreSQL connections. (a) *Connector-execution guard:* a context manager active only around `Connector.fetch()` (and the fixture reader it calls) patches `socket.socket.connect/connect_ex`, `socket.create_connection` and `socket.getaddrinfo` to raise `NetworkAccessError`; it is keyed to a `contextvars` flag, so other threads (queue heartbeat, test fixtures) and code outside the window are unaffected. The connector contract is *pure*: `fetch()` receives its inputs through `FetchContext` and returns records; **all database and storage I/O happens in the handler outside the guarded window** (a connector that needs the database inside `fetch()` fails the test, which is the intended signal). (b) *Whole-path audit:* an end-to-end worker test in a **subprocess** installs a `sys.addaudithook` that records every `socket.connect`/`socket.getaddrinfo` event with its originating frames; the test passes only if every destination is the test PostgreSQL endpoint (host/port or Unix-socket path taken from `GEO_TEST_DATABASE_URL`) and **no recorded event has a `geo_connectors` frame on its stack**. (c) *Static:* `geo_connectors` imports no HTTP client, `socket`, `ssl`, `urllib*` or `rasterio` (T8). Both dynamic checks run in `disabled` and `fixture` modes.
- **T6** deletion and files: tombstones written in the deleting transaction with `INSERT … ON CONFLICT (storage_key) DO NOTHING`; files removed after commit; simulated failure after commit → success with `files_pending_cleanup: n`, drain completes it; double and concurrent drains are safe; a replacement asset (new key) is never removed; `storage_key` uniqueness and immutability enforced; path-traversal keys rejected; **`make reconcile-assets` drains tombstones and only *reports* orphan files and rows with missing files — no destructive orphan deletion exists in 3a (test: the command has no delete mode and removes nothing unreferenced)**.
- **T7** concurrency and errors (PostGIS), amended by ADR-0014 r5 (2026-10-05). Real concurrency evidence uses several real database sessions synchronised through observable database state (`pg_locks` with `granted = false`, or a session returning), never `sleep`; every wait has a bounded timeout; tests must be shown able to fail (mutation check). Fault-injection tests are labelled **simulated** and are not counted as concurrency evidence. None needs superuser privileges in normal CI.
  - *Real concurrency:* **T-D1** sequential matrix (each job status × delete AOI/project; queued/running → 409 and nothing changes); **T-D2** job-insert-vs-delete both orders; **T-D3** claim-vs-delete; **T-D4** status change between the diagnostic read and the lock (a committed update by a second session at a test seam) → decision from the locked rows, 409, nothing deleted; **T-D5** *negative control*: a lock-all-jobs-with-waiting variant against a worker holding a key-share on the job and waiting for the AOI produces `40P01` (shows the harness can see the cycle); **T-D6** corrected deleter vs asset insert on a `running` job returns 409 while the worker transaction is still open; **T-D7** corrected deleter vs a late asset insert on a *terminal* job, with both foreign-key lock orders forced explicitly → `55P03` refusals, 503 within the attempt budget, no `40P01` in either session; **T-D8** project-delete-vs-AOI-create both orders (and vs a job insert in a child AOI); **T-D9** concurrent deleters (AOI/AOI, project/AOI inside it, project/project) end in a serial-equivalent state; **T-D10** enqueue (holding the advisory lock) vs deleter, plus a static check that deletion code never calls `pg_advisory*`; **T-D12** tombstone consistency after commit/rollback incl. `ON CONFLICT DO NOTHING`; **T-D13** direct-SQL checks: RESTRICT on every reference, and every involved foreign key is immediate (`condeferrable = false`), enabled and validated.
  - *Simulated faults (labelled as such):* **T-D11** injected `40P01`/`40001`/`55P03` at every statement index → the whole transaction restarts, nothing is issued on an aborted transaction, the result is all-or-nothing, and 503 follows when the single total budget `MAX_TX_ATTEMPTS = 3` (ADR §7.6) is exhausted; **T-D15** exact-id-set and affected-row-count checks use an explicit **test seam** in the deletion function (an injectable hook between locking and deleting that can add or remove a row inside the test's own transaction scope) — no superuser, no `session_replication_role`.
  - *Policy regression check (not a database guarantee):* **T-D14** statically checks that every status-changing `UPDATE job … SET status` in non-test code has a non-terminal source-status predicate; it fails if a terminal → non-terminal path is added without updating the ADR.
  - Also: insert-vs-delete, claim-vs-delete and project-delete-vs-AOI-create as above; the **level-by-level lock order** of ADR-0014 §7.5 (barrier-controlled interleavings); every row of the ADR §7.6 translation table, including that an **unexpected** integrity failure surfaces as 500 `integrity_error` (logged, not hidden, not mapped to 404).
- **T8** architecture: backend does not import `geo_connectors`; `geo_connectors` imports no HTTP client, `socket`, `rasterio`; no third-party dependency added (lockfile changes limited to the new workspace member).
- **T9** guards: forbidden-term scan covers the new code; assets carry no confidence/score; output-schema allow-list (plan §7.12–§7.13 applicable parts).
- **T10** `make ci-full` green locally and GitHub Actions green including `e2e`; **T11** licence register check passes with no new third-party package.

**CP2 status (2026-10-05, owner-authorised; Claude's reading of the checkpoint, not an acceptance):** *Implemented:* P3-02 migration 0004; the AOI-bound `enqueue` contract (queue layer; the HTTP jobs API is unchanged); the r5 deletion rewrite at job level; T1 (all five cases); T2 job-level cases; T-D1, T-D2, T-D3, T-D4, T-D5, T-D6 and T-D7 (real sessions, **lock holder emulated** — no asset table yet), T-D8, T-D9, T-D10, T-D11 and T-D15 (**simulated** faults/seam), T-D13 (job/aoi foreign keys), T-D14 (policy check). *Pending (need migration 0005 or the jobs API):* T2 asset cases; T-D12 (tombstones); real asset-insert variants of T-D6/T-D7; the asset and tombstone steps of the deletion algorithm; T3 (API); T4; T6; T9–T11 completion. P3-03 (jobs API), P3-04's remaining parts, P3-06a, P3-07, P3-09 are not started.

**Gates before 3a may start:** (1) ADR-0014 **Accepted** — **met 2026-10-05**; (2) the owner's acceptance of this 3a scope — **met 2026-10-05 (scope only)**; (3) the owner's explicit, bounded **start instruction** for Phase 3a only — **outstanding**, and it should state the implementation branch/base (this documentation branch is unmerged). F-1 is **not** a gate for 3a (owner exception, 2026-10-05). **Additional gates before any live connector slice:** F-1 closed; D8 readiness R1–R8 (§8a); exact host/port allowlist and application/network controls approved; start instruction for that slice.

### 3b — STAC catalogue search
| P3-05b | HTTP client selected per ADR-0014 §9 (evaluation note) and wrapped; offline tests R-a–R-f; budgets/timeouts/size caps (moved from 3a) | tests pass; no live request |
| P3-06b | Cache (key, TTL, size cap, eviction) (moved from 3a) | cache-hit-makes-zero-requests test |
| P3-04b | Provider definitions with approved hosts, budget settings, `ENABLED_CONNECTORS` (moved from 3a) | owner-approved allowlist only |
| P3-10 | Verify assumptions: write `connectors-live-check` (read-only, tiny) | script exists; run under the §8a route (B if approved, otherwise **owner runs it**) |
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
5. Empty results end the job in the existing queue status `insufficient_data` with an explanation (an ingestion/queue status, not a scientific result: no `result` row, no confidence or interpretation — see T4); provider errors yield `failed` with a reason; no silent defaults.
6. Hostile responses and files (list in §3.6) are rejected without crashing the worker or leaking paths.
7. Job↔project/AOI linkage and deletion rules (§3.1) are enforced and tested; running jobs block deletion.
8. UI shows what is sent to the provider before submission, labels provider-reported values as such, and shows no analysis.
9. The browser smoke test (CI `e2e`) covers the catalogue flow in fixture mode; no CI job touches the network except package/browser installation.
10. No connector, output or UI string contains analysis/scoring vocabulary (forbidden-term scan extended); backend does not import `geo_connectors`.
11. Live behaviour is either verified by the owner's `connectors-live-check` report (attached to the phase report) or explicitly reported as **unverified**; Earth Search and Copernicus GLO-30 remain labelled **tentative** until then.
12. Out-of-scope enforcement (§0b) is tested: import allow-lists for `geo_connectors` and the backend, output-schema allow-list, extended forbidden-vocabulary scan, `disabled` default, no EE code path reachable.
13. Only the operations in §0c exist: a test proves raster clipping preserves values and grid (no resampling) and vector normalisation changes only CRS/orientation, never attributes.

## 8. Final decision table (D1–D12)

Basis: the owner replied **"Approved with constraints"** to the plan and its recommendations, and listed six constraints (docs-only pass; scope summary; strict out-of-scope; ADR-0014 stays Proposed; Earth Search and GLO-30 tentative; no implementation). **This table records that reading; a decision marked OPEN has not been decided.** Please correct any row that misstates your intent.

| # | Decision | Outcome | Condition / constraint | Status |
|---|---|---|---|---|
| D1 | Slice order and review gates (3a→3b→3c→3d→3f; 3e blocked) | Approved as planned | Owner review after every slice; no slice starts without release | **Approved** |
| D2 | ADR-0014: `workers/connectors` package, `data_asset` entity, job↔project/AOI columns | Direction accepted at plan level | ADR-0014 was to stay Proposed until explicitly marked Accepted (2026-10-04 constraint); **explicitly Accepted by the owner on 2026-10-05** (revision 4, not implemented); no code before a start instruction | **Plan accepted; ADR Accepted (2026-10-05); not implemented** |
| D3 | `rasterio` (BSD-3, bundles GDAL) as a worker dependency | Approved in principle | Image-size impact measured in slice 3a and reported; licence verified from metadata at install | **Approved (conditional)** |
| D4 | Default catalogue provider | **Earth Search = TENTATIVE default** | Unverified; not enabled/advertised until live verification (§1) and owner confirmation; alternates: Planetary Computer, Copernicus Data Space | **Tentative** |
| D5 | DEM source | **Copernicus DEM GLO-30 = TENTATIVE default** | Unverified; licence/attribution, vertical datum and tile layout to be confirmed live | **Tentative** |
| D6 | `CONNECTOR_MODE` default `disabled`; `live` explicit opt-in | Approved | Tested default; `live` needs `ENABLED_CONNECTORS` | **Approved** |
| D7 | Budget defaults in §3.3 | Approved as provisional safeguards | Not measured; same status as ADR-0008 limits | **Approved (provisional)** |
| D8 | Live verification: **strategy** (resolved) and **readiness** (pending) | **Strategy resolved 2026-10-05: option D** — Phase 3a is fixtures-only; live verification is mandatory before accepting the live connector slices 3b and DEM (and any other live slice). Route B (cloud-environment host allowlist) preferred if the environment supports it, **subject to separate owner approval of the exact allowlist**; otherwise route A (owner runs the read-only check) | Not acceptance of live connector functionality; no host approved; no network access expanded; see §8a | **Strategy RESOLVED; readiness PENDING** |
| D9 | Earth Engine | Remains **blocked**; **no execution** | Needs the owner's written eligibility validation (ADR-0004), then a separate approval; not part of Phase 3 acceptance | **Blocked** |
| D10 | Geology/occurrence data in Phase 3 = user-supplied vector layers only | Approved | National-survey connectors wait for the Phase 5 region decision | **Approved** |
| D11 | CI `e2e` gains a worker process and fixture mode | Approved | No live network in CI | **Approved** |
| D12 | Phase 5 region/pilot-area gate and the "no analysis" rule unchanged | Confirmed | See §0b | **Confirmed** |

## 8a. D8 — live verification: strategy and readiness (2026-10-05)

**Strategy (decided by the owner, 2026-10-05): option D.**
- **Phase 3a is fixtures-only:** `CONNECTOR_MODE` is `disabled` or `fixture`; no live code path is enabled; no provider is contacted.
- **Live verification is mandatory before accepting** each live connector slice — 3b (STAC) and DEM (3c), and any other slice that talks to a provider.
- **Route:** B (host allowlist in the cloud environment's network settings, so the check can be run in-session) is preferred *if the environment supports it*, and only **after the owner separately approves the exact `(host, port)` allowlist**; otherwise route A (the owner runs the read-only check on a machine with internet access and returns the report).
- **Not decided / not implied:** network access is **not** expanded now; **no host name is approved** (names that appeared in this repository or in conversation are unverified); selecting the strategy is **not** acceptance of live connector functionality and **not** authorization to start Phase 3 or Phase 3a.

**Readiness (pending) — prerequisites before any live verification:**

| # | Prerequisite | Status |
|---|---|---|
| R1 | Exact endpoints and every required host (including redirect, CDN and object-store hosts) and ports, **confirmed from official provider documentation**, with source URL and retrieval date | PENDING |
| R2 | Terms of service, data and API licences, and attribution requirements, from official sources | PENDING |
| R3 | Request limits and any applicable costs (quotas, rate limits, accounts/keys, egress or requester-pays charges); any non-zero cost needs the owner's approval first (`CLAUDE.md` §5) | PENDING |
| R4 | Owner approval of the exact host/port allowlist (route B) **or** owner review of the check script and the owner running it (route A) | PENDING |
| R5 | Concrete application **and** network controls for the specific approved hosts approved by the owner (ADR-0014 §9 is accepted as design only; the live path must not exist before this) | PENDING |
| R6 | An explicit start instruction covering the slice that will be verified | NOT GIVEN |
| R7 | Follow-up F-1 (Phase 0 documentation consistency) closed | OPEN |
| R8 | HTTP-client selection note and offline tests R-a–R-f of ADR-0014 §9 passing; licence review of ADR-0014 §10 recorded | PENDING |

**Constraints on every verification run:** read-only requests; **no private AOI geometry is sent** — only small fixed queries or public example data; no load testing and no deliberate probing of rate limits (stop and report on the first throttle or error); no credentials; the report records time, endpoints, responses' relevant fields, licence/attribution text found and observed limits; a mismatch with this plan is handled by an ADR-sized decision, not a silent switch (§1.3).

**Acceptance consequence:** a live connector slice cannot be accepted without a recorded live-verification report; Phase 3a can be accepted at most as "fixture-verified".

Still required before any implementation: (0) *[recorded 2026-10-05, owner decisions D-1…D-4]* reconciliation of the prerequisite phases' acceptance records; (1) an explicit, bounded instruction to start Phase 3a — **outstanding**; (2) ADR-0014 **Accepted** — **met 2026-10-05**; (3) D8 — strategy resolved 2026-10-05; live-verification readiness (§8a) is required before accepting live slices, not before the fixtures-only 3a. Also: Phase 0 follow-up F-1 is non-blocking for fixtures-only 3a by the owner's narrow exception and must be closed before any live connector slice. None of this authorises Phase 3a to start.

## 9. Out of scope

Canonical, strict list: **§0b**. Permitted operations: **§0c**. (Not repeated here to avoid two lists drifting apart.)

## 10. Change log of this document
- 2026-10-04 (proposal): first full plan.
- 2026-10-04 (final planning pass, after "approved with constraints"): added scope summary, strict out-of-scope (§0b) and permitted operations (§0c); marked Earth Search and Copernicus GLO-30 **tentative**; added acceptance criteria 12–13; replaced the questions with the final D1–D12 decision table; ADR-0014 kept **Proposed**; no implementation.
- 2026-10-05 (fourth owner message, documentation only): ADR-0014 **Accepted** (revision 4, not implemented); 3a scope accepted as scope (not a start instruction); T4 empty-catalogue contract, T5 connector-scoped no-network test, T6/T7 corrections; orphan cleanup report-only; licence acknowledgements moved to `docs/licence-acknowledgements.toml`; no code, dependency, generator or network change.
- 2026-10-05 (third owner message, documentation only): ADR-0014 revision 3; 3a re-scoped to fixtures-only with acceptance tests T1–T11 and start gates (§6); R7 (F-1 closed) and R8 (client selection, ADR §9/§10) added to §8a readiness; F-1 designated non-blocking for fixtures-only 3a only; canonical ADR status vocabulary; no code, dependency or network change.
- 2026-10-05 (second owner message, documentation only): D8 strategy resolved (option D) and readiness split out (§8a); ADR-0014 revision 2 drafted for review (not accepted); Phase 2 "Actions green" item clarified and ticked in `TASKS.md`; Phase 0 follow-up F-1 recorded; no code, dependency or network change.
- 2026-10-05 (owner decisions recorded): prerequisite-phase acceptance decisions D-1…D-4 recorded; the block now rests on an explicit start instruction, an owner decision on ADR-0014 and decision D8 (OPEN); design unchanged.
- 2026-10-04 (status-wording reconciliation): status set to blocked pending prerequisite acceptance reconciliation; corrected the prerequisite statement (see the top of this document); D8 remains **OPEN**; design unchanged.
