# Architecture

Status: Draft v0.1 · Changes via ADR (`docs/adr/`).

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
- Interface: `run(job_input) -> EngineResult` (typed, defined in `packages/schemas`).
- Workers read/write via storage and DB interfaces; they never import backend code.
- Engines are idempotent and resumable where feasible; hard timeouts and memory limits.

### Data layer
- **PostGIS**: AOIs, jobs, targets, evidence references, provenance, user annotations.
- **File storage**: rasters as Cloud-Optimised GeoTIFF; uploads; reports. Local filesystem only in V1 via `StorageBackend` (`put/get/exists/delete/open_path`); logical keys, traversal-safe (ADR-0006). A later S3-compatible backend is a swap behind the same interface.
- **Cache**: deterministic keys (source + AOI hash + params + version) to avoid re-fetching.

### Queue
- The `job` table in PostgreSQL is the queue (ADR-0007): transactional enqueue, atomic claim with `FOR UPDATE SKIP LOCKED`, lease + heartbeat, crash recovery, attempt limits, hard timeout via child process, cancellation. Accessed only through a `JobQueue` interface so it can later be replaced by RQ/Celery.
- Defaults: 1 worker, poll every 2 s, `MAX_QUEUED_JOBS=10`.

### Shared schemas (`packages/schemas`)
- JSON Schema / OpenAPI is the source of truth; Pydantic and TS types generated.
- Core schemas: `AOI`, `Job`, `Target`, `ResultEnvelope`, `Provenance`, `Evidence`, `Disclaimer`.

## 2a. AOI handling (Phase 2, ADR-0012)

`apps/backend/src/app/aoi/`: `geometry.py` (construction, validation, geodesic area, UTM zone), `parsers.py` + `archive.py` (GeoJSON / KML / KMZ / zipped Shapefile, in-memory, hardened), `service.py` (request/upload → normalised draft), `repository.py` (PostGIS persistence). Endpoints under `/api/v1/aois`: `limits`, `preview` (validate without saving), `POST` (create), `upload` (multipart, `?preview=true`), `GET` list/detail, `DELETE`. Contracts (`Aoi`, `AoiDraft`, `AoiSummary`, `AoiList`, `AoiLimits`, request types) live in `packages/schemas`. An AOI is a validated outline plus bookkeeping; it is not a scientific result and carries no envelope fields. The frontend (`AoiWorkbench`, `MapView` on MapLibre) draws sketches and overlays only; numeric forms are the accessible alternative to drawing.

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

## 5. Connector design (Phase 3)

Uniform interface: `describe()`, `estimate_cost(aoi, window)`, `fetch(aoi, window) -> Assets+Provenance`. Connectors declare quota, licence, what AOI information is sent to the provider, and offline-mock fixtures. STAC/open sources are the default. Earth Engine is optional, behind `ENABLE_EARTH_ENGINE` (default false), experimental/non-commercial only (ADR-0004).

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
| `packages/pycommon` (ADR-0011) | Shared Python: config, `StorageBackend`, `JobQueue`, generated envelope models |
| `workers/runner` | Generic worker loop + `noop` handler |
| `infrastructure/` | Docker/CI |
| `tests/{unit,integration,scientific}` | Tests |

## 9. Known architectural risks
See `docs/risk-register.md` (scaling, infra, data availability).
