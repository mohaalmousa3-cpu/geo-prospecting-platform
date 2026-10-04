# Architecture

Status: Draft v0.1 · Changes via ADR (`docs/adr/`).

## 1. Overview

```
 Browser (Next.js)
   ├─ MapLibre GL (2D)     ├─ CesiumJS (3D)
        │ HTTPS (REST/JSON, optional SSE for job status)
        ▼
 FastAPI backend ──── PostgreSQL + PostGIS   (AOI, jobs, targets, provenance)
        │                    ▲
        │ enqueue            │ read/write results
        ▼                    │
   Redis queue ──► Workers ──┴──► Object storage (COG rasters, uploads, reports)
                     │
                     └──► External data (STAC, open DEM/geology APIs, optional Earth Engine)
```

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
- **Object storage**: rasters as Cloud-Optimised GeoTIFF; uploads; reports. Default local volume or MinIO (ADR pending). Interface abstracted for S3-compatible swap.
- **Cache**: deterministic keys (source + AOI hash + params + version) to avoid re-fetching.

### Queue
- Redis-backed; library chosen by ADR (Celery / Dramatiq / RQ / arq). Requirements: retries, timeouts, priorities, per-engine routing, visibility of state.

### Shared schemas (`packages/schemas`)
- JSON Schema / OpenAPI is the source of truth; Pydantic and TS types generated.
- Core schemas: `AOI`, `Job`, `Target`, `ResultEnvelope`, `Provenance`, `Evidence`, `Disclaimer`.

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

## 4. Job lifecycle

`created → validated → queued → running → (succeeded | failed | cancelled | insufficient_data)`

`insufficient_data` is a normal terminal state with an explanation.

## 5. Connector design (Phase 3)

Uniform interface: `describe()`, `estimate_cost(aoi, window)`, `fetch(aoi, window) -> Assets+Provenance`. Connectors declare quota, licence, and offline-mock fixtures. Earth Engine is optional, behind a feature flag.

## 6. Cross-cutting

- **Provenance**: recorded for every dataset and processing step.
- **Reproducibility**: pinned dependency versions; container digests recorded.
- **Observability**: structured logs with job id; metrics later.
- **Security**: upload hardening (zip-bomb limits, path traversal, geometry validation); secrets via environment only; auth deferred (Open Question).
- **Config**: environment variables only (`.env.example`).
- **CRS**: store EPSG:4326; compute in a local projected CRS (UTM) chosen per AOI; always record CRS.

## 7. Deployment

- Dev: Docker Compose (postgis, redis, backend, worker(s), frontend, optional minio).
- Production: deferred to ADR; must not require paid managed services by default.

## 8. Directory mapping

| Path | Role |
|---|---|
| `apps/frontend` | UI |
| `apps/backend` | API |
| `workers/<engine>` | Engines |
| `packages/schemas` | Contracts |
| `infrastructure/` | Docker/CI |
| `tests/{unit,integration,scientific}` | Tests |

## 9. Known architectural risks
See `docs/risk-register.md` (scaling, infra, data availability).
