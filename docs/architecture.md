# Architecture

Status: living document, **aligned with the accepted Phase 3a baseline (fixtures-only, accepted 2026-10-06)** — §5a describes what is implemented; §1–§5 keep the original design intent, and anything marked *deferred* or *design intent* is **not implemented**. No live provider, HTTP client, egress control, cache or scientific engine exists. Reconciliation record: `docs/phase-reports/acceptance-reconciliation.md` §9b. · Changes via ADR (`docs/adr/`).

## 1. Overview

```
 Browser (Next.js)
   ├─ MapLibre GL (2D)     ├─ CesiumJS (3D)
        │ HTTP on loopback (REST/JSON; polling for job status)
        ▼
 FastAPI backend ──── PostgreSQL + PostGIS   (AOI, jobs = the queue, targets, provenance)
        │ insert job row            ▲  claim (SKIP LOCKED) / heartbeat / complete
        │                           │
        └──────────────────────► Workers ──► Local filesystem storage (COG rasters, uploads, reports)
                                    │
                                    └──► External data (STAC, open DEM/geology APIs, optional Earth Engine)
```

V1 constraints: no authentication (ADR-0005), local storage (ADR-0006), PostgreSQL-backed queue (ADR-0007). No Redis, no MinIO.

*Implementation note:* the "External data (STAC, open DEM/geology APIs, optional Earth Engine)" path in the diagram is **design intent and is not implemented** — as built, workers read only committed synthetic fixtures (§5a). The tracks for engines and "targets" are likewise future work.

## 2. Components

### Frontend (`apps/frontend`)
- Next.js + TypeScript. Server components only where useful; map components client-side.
- MapLibre for 2D, CesiumJS for 3D (lazy-loaded; heavy bundle).
- Consumes generated types from `packages/schemas`.
- Renders confidence/uncertainty/disclaimer as first-class UI elements (not optional).

### Backend API (`apps/backend`)
- FastAPI, versioned prefix `/api/v1`.
- Responsibilities: AOI validation/storage, job creation/status, result retrieval, provenance, export.
- No long-running or heavy computation in request handlers.
- Enforces compute budgets (AOI area, time window, scene count) at job creation.
- Refuses to serve any result lacking the mandatory result envelope.

### Workers (`workers/*`)
- Each engine is an independent Python package with its own dependency set and (where needed) Docker image — isolates heavy/conflicting geo stacks (GDAL, MintPy, pyGIMLi).
- Interface: `run(job_input) -> EngineResult` (typed, defined in `packages/schemas`) — **engine contract, planned**; the handler contract that exists today (`handler(payload[, context]) -> HandlerResult`, registered by import-path string) is described in §5a.
- Workers read/write via storage and DB interfaces; they never import backend code.
- Engines are idempotent and resumable where feasible; hard timeouts and memory limits.

### Data layer
- **PostGIS**: as built — `project`, `aoi`, `job` (the queue), `data_asset`, `storage_tombstone`, `provenance`, `result` (no writer yet); planned — targets, evidence references, user annotations. Schema changes are Alembic migrations 0001–0006 (§5a).
- **File storage**: rasters as Cloud-Optimised GeoTIFF; uploads; reports. Local filesystem only in V1 via `StorageBackend` (`put/get/exists/delete/open_path`); logical keys, traversal-safe (ADR-0006). A later S3-compatible backend is a swap behind the same interface.
- **Cache**: deterministic keys (source + AOI hash + params + version) to avoid re-fetching — **design intent; no cache exists** and none is in the initial live-slice scope unless separately approved.

### Queue
- The `job` table in PostgreSQL is the queue (ADR-0007): transactional enqueue, atomic claim with `FOR UPDATE SKIP LOCKED`, lease + heartbeat, crash recovery, attempt limits, hard timeout via child process, cancellation. Accessed only through a `JobQueue` interface so it can later be replaced by RQ/Celery.
- Defaults: 1 worker, poll every 2 s, `MAX_QUEUED_JOBS=10`.

### Shared schemas (`packages/schemas`)
- JSON Schema / OpenAPI is the source of truth; Pydantic and TS types generated.
- Core schemas: `AOI`, `Job`, `Target`, `ResultEnvelope`, `Provenance`, `Evidence`, `Disclaimer`.

## 2a. AOI handling (Phase 2, ADR-0012)

`apps/backend/src/app/aoi/`: `geometry.py` (construction, validation, geodesic area, UTM zone), `parsers.py` + `archive.py` (GeoJSON / KML / KMZ / zipped Shapefile, in-memory, hardened), `service.py` (request/upload → normalised draft), `repository.py` (PostGIS persistence). Endpoints under `/api/v1/aois`: `limits`, `preview` (validate without saving), `POST` (create), `upload` (multipart, `?preview=true`), `GET` list/detail, `DELETE`. Contracts (`Aoi`, `AoiDraft`, `AoiSummary`, `AoiList`, `AoiLimits`, request types) live in `packages/schemas`. An AOI is a validated outline plus bookkeeping; it is not a scientific result and carries no envelope fields. The frontend (`AoiWorkbench`, `MapView` on MapLibre) draws sketches and overlays only; numeric forms are the accessible alternative to drawing.

## 2b. Projects (Phase 2.5, ADR-0013)

`project` is the container that owns AOIs and, in later phases, jobs and outputs; see `docs/data-model.md` for relationships, deletion rules and the planned job/output attachment. API: `/api/v1/projects` (create, list, get, delete with explicit `delete_aois`). AOIs are saved into a project (`project_id` required to save, not to preview). The frontend has a minimal project bar (select / create / delete). The map's basemap is chosen through the provider abstraction in `apps/frontend/src/lib/basemap.ts` (`osm` | `xyz` | `none`).

## 3. Result envelope (mandatory)

Every layer/target returned by the API includes:

| Field | Meaning |
|---|---|
| `kind` | `prospectivity` \| `anomaly` \| `evidence` \| `geophysics_model` (never `confirmed_*`) |
| `value` | score/class |
| `confidence` | categorical (low/moderate/high) + method note |
| `uncertainty` | quantitative where possible; method stated; or explicit `not_quantified` with reason |
| `evidence[]` | supporting inputs and counter-evidence |
| `explanation` | structured + rendered text |
| `sources[]` | dataset, version, acquisition date, licence, URL |
| `provenance` | run id, parameters, code version, environment digest |
| `depth` | present only if `depth_basis` ∈ {`field_geophysics`, `direct_verification`} |
| `disclaimer_id` | reference to mandatory disclaimer text |
| `validation_status` | `unvalidated` only in V1 (ADR-0010) |
| `calibration_status` | `uncalibrated` by default (ADR-0009) |
| `engine_status` | `experimental` until validated (ADR-0009) |
| `deposit_model` | gold results only: `orogenic` (ADR-0003); plus `applicability` ∈ applicable / applicability_unknown |

## 4. Job lifecycle

API-side (synchronous, before insert): request received → limits and AOI validated (ADR-0008) → job row inserted.
Persisted statuses: `queued → running → (succeeded | failed | cancelled | insufficient_data)`; an expired lease returns `running → queued` until `max_attempts`, then `failed`.

`insufficient_data` is a normal terminal state with an explanation.

## 5. Connector design (Phase 3) — original outline (design intent)

Uniform interface: `describe()`, `estimate_cost(aoi, window)`, `fetch(aoi, window) -> Assets+Provenance`. Connectors declare quota, licence, what AOI information is sent to the provider, and offline-mock fixtures. STAC/open sources are the default. Earth Engine is optional, behind `ENABLE_EARTH_ENGINE` (default false), experimental/non-commercial only (ADR-0004). **This outline predates Phase 3a; the implemented interface is `fetch(FetchContext) -> FetchResult` (§5a), and `describe()`/`estimate_cost()`, provider definitions and quotas are deferred to the live slices.**

## 5a. Phase 3a as built (fixtures-only; accepted 2026-10-06)

Binding records: ADR-0014 (and its CP3/CP4/closure records), `docs/connectors.md`, `docs/data-model.md`, `docs/job-lifecycle.md`. Nothing here is a scientific component: the staged data are inputs, not results.

**Backend API boundary (`apps/backend`).** Routers under `/api/v1`: `health`, `jobs`, `projects`, `aois`, `assets`, `connectors`. The backend validates requests, enforces ADR-0008 limits server-side, creates jobs through the `JobQueue` interface and serves metadata and stored files of staged assets; it **never imports `workers/*`** (`geo_connectors`, `runner`; tested in `tests/unit/test_architecture.py`). `GET /connectors` is a static, read-only capability description (no host, URL or credential). There is no asset-creation route and no result route.

**Persistence and migrations (`packages/pycommon`, PostgreSQL + PostGIS).**
| Migration | Adds |
|---|---|
| 0001–0003 | initial schema (`aoi`, `job`, `result`, `provenance`), AOI details, `project` |
| 0004 | `job.aoi_id`/`job.project_id` (both set or both NULL; every non-`noop` job needs an AOI), composite foreign key to `aoi(id, project_id)` (RESTRICT), so a job's project always equals its AOI's project |
| 0005 | `data_asset` (composite foreign keys to its AOI and, if linked, its job; unique `storage_key`; `UNIQUE (job_id, kind, request_hash)` for job-bound assets), `storage_tombstone`, `provenance.job_id` nullable |
| 0006 | `result.job_id` and `provenance.job_id` foreign keys become `RESTRICT` (were `CASCADE`) |

**Relationships.** `project 1—* aoi`; `aoi 1—* job` (project derived from the AOI, never supplied by a client); `aoi 1—* data_asset`; `job 0..1—* data_asset`; `data_asset 1—1 provenance`. `result` rows are scientific-result records that always need a job; **no code writes them yet**. `data_asset` rows are staged inputs (catalogue metadata): they carry no confidence, score or interpretation and are never results.

**Job queue and worker boundary.** The `job` table is the queue (ADR-0007). `workers/runner` claims a job, starts the registered handler in a spawned child process (heartbeat, lease, hard timeout, cancellation) and completes the job **after** the handler returns. Handlers are registered **by import-path string** (`noop`, `catalog_search` → `geo_connectors.handler:catalog_search`); the runner never imports connector code. The child receives a job context (`job_id`, `worker_id`, `aoi_id`, `project_id`). Handler-process death and exceptions marked `retryable` are requeued while attempts remain (`docs/job-lifecycle.md`).

**`geo_connectors` (`workers/connectors`, workspace package).** Pure `Connector.fetch(FetchContext) -> FetchResult` contract, registry and `CONNECTOR_MODE` resolution, an offline fixture connector over two committed synthetic fixtures, the `catalog_search` handler, `build_provenance_record`, a versioned `request_hash`, errors. Depends on `geo_common` only; no third-party dependency; installed in the **worker** image (`EXTRA_PACKAGE`), not in the backend image.

**`catalog_search` path and `CONNECTOR_MODE`.** `POST /jobs` → request validation → `CONNECTOR_MODE` gate → AOI lookup → enqueue (project derived from the AOI). Modes: `disabled` (default) → API `409 connectors_disabled`, nothing queued; `fixture` → queued and served from the committed fixtures; `live` → API `501 connector_live_not_available` (a worker started in `disabled`/`live` fails the job explicitly). In the worker: read the AOI → `fetch()` inside the fetch window (no database, storage or socket I/O) → zero matches end the job as `insufficient_data` with no asset, provenance or result row → otherwise stage the file and publish one `scene_catalog` asset with its provenance in one verified transaction (job running, owned, not cancel-requested). Re-runs of the same job are idempotent under `request_hash`.

**Storage, tombstones, reconciliation.** `LocalStorage` (`STORAGE_LOCAL_PATH`): files are written to a staging area (`.staging/`), flushed and renamed atomically under keys `projects/<project>/aois/<aoi>/jobs/<job>/<asset>.json`; keys are never reused. Deleting rows writes `storage_tombstone` entries **in the same transaction**; files are removed after the commit by a drain (also run at backend and worker start-up); a failed cleanup never fails a committed deletion. `make reconcile-assets` drains tombstones and then only **reports** unreferenced files, rows without a file and staging files — there is no destructive orphan cleanup.

**Deletion guards.** AOI/project deletion is one transaction in a fixed lock order (project → AOIs → jobs → assets) with whole-transaction retry. Refusal order: `has_active_jobs` → `has_results` → `needs_cascade` / `project_not_empty`. `has_results` protects every `result` row and every `provenance` row of the target jobs unless that exact row belongs to an asset selected for deletion in the same operation. The `RESTRICT` foreign keys of migration 0006 are a second line behind this application guard, not a replacement; `TRUNCATE … CASCADE`, `DROP` and similar administrative operations are outside both.

**Explicitly absent (not implemented):** live networking and any provider integration; an HTTP client or address-pinning transport; egress enforcement (Compose has **no** egress firewall — ADR-0014 §9); a cache; `rasterio`/DEM; user-vector upload; Earth Engine; any scientific engine, scoring or interpretation; any UI for jobs, assets or connectors.

**Deferred live-slice design points (design intent only — nothing below exists):** HTTP-client/transport selection and the R-a…R-f outbound protections (ADR-0014 §9); provider definitions with owner-approved `(host, port)` pairs; budgets enforced on real requests; owner-approved application and network egress controls; a recorded live-verification report. Each needs F-1 closed, D8 readiness R1–R8 (`docs/phase-3-plan.md` §8a) and the owner's explicit start instruction. **No live architecture is approved.**

## 6. Cross-cutting

- **Provenance**: recorded for every dataset and processing step.
- **Reproducibility**: pinned dependency versions; container digests recorded.
- **Observability**: structured logs with job id; metrics later.
- **Security**: upload hardening (zip-bomb limits, path traversal, geometry validation); secrets via environment only; **no authentication in V1 (ADR-0005)** — loopback-bound ports, CORS allow-list, never publicly exposed.
- **Config**: environment variables only (`.env.example`).
- **CRS**: store EPSG:4326; compute in a local projected CRS (UTM) chosen per AOI; always record CRS.

## 7. Deployment

- Dev: Docker Compose (postgis, backend, worker, frontend) with ports published on `127.0.0.1` only.
- Production: deferred to ADR; must not require paid managed services by default.

## 8. Directory mapping

| Path | Role |
|---|---|
| `apps/frontend` | UI |
| `apps/backend` | API |
| `workers/<engine>` | Engines |
| `packages/schemas` | Contracts |
| `packages/pycommon` (ADR-0011) | Shared Python: config, migrations 0001–0006, `JobQueue`/PostgreSQL queue, `StorageBackend`/`LocalStorage`, staged-asset persistence (`assets_pg`), transaction helpers, generated models |
| `workers/runner` | Generic worker loop; registers the `noop` and `catalog_search` handlers by import path |
| `workers/connectors` | `geo_connectors`: fixtures-only data-access package (§5a) |
| `scripts/` | `reconcile_assets.py` (report-only), schema/licence/audit tooling, image smoke test |
| `infrastructure/` | Docker/CI |
| `tests/{unit,integration,scientific}` | Tests |

## 9. Known architectural risks
See `docs/risk-register.md` (scaling, infra, data availability).
