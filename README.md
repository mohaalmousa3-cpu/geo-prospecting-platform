# geo-prospecting-platform

A scientific web platform for **prospectivity and anomaly screening** from remote-sensing, geological, terrain and thermal data — for gold-related targets, cavity/void-related targets and thermal anomalies — with explicit confidence and uncertainty.

> **Status: Phases 1–2 accepted (with follow-ups); Phase 2.5 (projects, basemap abstraction) implemented, awaiting acceptance; Phase 3 not started.** The platform can define, validate, store and display Areas of Interest inside projects. **No analysis, scoring, remote-sensing, Earth Engine or scientific output exists yet.**

## ⚠️ Scientific disclaimer

Outputs are **prospectivity / anomaly layers**. They are **not** confirmation of gold, caves or voids. Satellite and thermal data alone cannot confirm either. Subsurface depth is shown only when derived from uploaded field geophysics or direct verification. All results include confidence, uncertainty, explanation and source metadata. Field verification is required before any decision. See [`docs/scientific-constraints.md`](docs/scientific-constraints.md).

## What it will do

- Define an AOI by coordinates + radius, drawn rectangle/polygon, or KML/KMZ/GeoJSON/Shapefile upload.
- Gather EO, terrain, thermal and geological data from open sources.
- Produce ranked, explained targets with confidence and uncertainty.
- Visualise in 2D (MapLibre) and 3D (CesiumJS).
- Later: ingest and interpret ERT, GPR, IP and magnetic field data.

## Planned stack

Next.js · FastAPI · PostgreSQL/PostGIS (also the V1 job queue) · background workers · Docker Compose · MapLibre · CesiumJS · local filesystem storage. No Redis, no MinIO, no authentication in V1.
Scientific tooling to be integrated (licence review first): EIS Toolkit, EnMAP-Box concepts, Landsat LST workflows, MintPy, pyGIMLi, ResIPy, GPRPy, GemPy. Google Earth Engine and STAC connectors later (EE optional).

## Repository layout

```
apps/
  frontend/        Next.js app (Phase 1+)
  backend/         FastAPI app (Phase 1+)
workers/           Background engines, one isolated module/image each
  runner/          Generic worker loop + noop handler
  thermal/ gold_prospectivity/ void_evidence/ geophysics/ insar/   (placeholders; not implemented)
packages/
  schemas/         Shared JSON Schema contracts (source of truth)
  pycommon/        geo_common: shared config, JobQueue/StorageBackend, envelope guard, migrations (ADR-0011; no analysis logic)
docs/              Architecture, science constraints, risks, ADRs
infrastructure/    Docker, CI, deployment config
data/              Local data only (git-ignored contents); samples/ for tiny fixtures
scripts/           Developer tooling
tests/             unit/ integration/ scientific/
```

## Development principles

1. **Phase by phase.** See [`TASKS.md`](TASKS.md). No work beyond the current phase.
2. **Science first.** Never overstate. Confidence/uncertainty/explanation/sources on every result.
3. **Free/open by default.** Paid services are optional and off by default.
4. **Modular and bounded.** Isolated engines, bounded compute, reproducible runs with provenance.
5. **Tested.** Including scientific guard tests that forbid unsupported claims.
6. **No secrets in the repo.** Use `.env` (ignored); see `.env.example`.

## Development quick start (Phase 1)

> **V1 has no authentication.** Run locally only. Compose publishes ports on `127.0.0.1`; never expose them publicly ([ADR-0005](docs/adr/0005-no-authentication-v1.md)).

Prerequisites: Docker with Compose, [`uv`](https://docs.astral.sh/uv/), Node 22 + npm.

```bash
cp .env.example .env              # then set POSTGRES_PASSWORD (placeholder values only; .env is git-ignored)
make up                           # postgis + migrate + backend + worker + frontend
curl http://127.0.0.1:8000/api/v1/health/ready
# frontend: http://127.0.0.1:3000   API docs: http://127.0.0.1:8000/docs
make down
```

Behind a TLS-intercepting proxy, set `PROXY_CA_BUNDLE=/path/to/ca.pem` before `make up` (build-time only).

Local checks (all of CI): `make sync && make ci`. Integration tests need PostGIS reachable at `GEO_TEST_DATABASE_URL`
(default `postgresql+pg8000://geo:geo@localhost:5432/geo_test`; the database and the `postgis` extension must be creatable by that user).

| Command | What |
|---|---|
| `make lint` / `make typecheck` | ruff, mypy |
| `make test` / `make test-integration` | unit tests / PostGIS-backed tests (queue concurrency, lease, retry, recovery, API, worker) |
| `make guard` | scientific guard tests (forbidden claims, envelope, repo policy) |
| `make schemas` / `make schemas-check` | regenerate / verify generated types from `packages/schemas` |
| `make licences` | verify the third-party licence register |
| `make frontend-check` | lint, typecheck, format, tests, build |
| `make e2e` | browser smoke test (Playwright → Next.js → FastAPI → PostGIS); needs a database `$E2E_POSTGRES_DB` and Chromium (`npx playwright install chromium` or `E2E_CHROMIUM_PATH`) |
| `make ci-full` | everything CI runs, including the browser smoke test |

The app contains **no scientific engine and no scientific output**: health checks, a `noop` job, the queue/worker, shared contracts, AOI input/validation/storage with a 2D map, and guard tests. Data model: [`docs/data-model.md`](docs/data-model.md) (project ↔ AOI ↔ future jobs ↔ outputs). Evidence: [`phase-2.5.md`](docs/phase-reports/phase-2.5.md), [`phase-1.md`](docs/phase-reports/phase-1.md), [`phase-1-closeout.md`](docs/phase-reports/phase-1-closeout.md), [`phase-2.md`](docs/phase-reports/phase-2.md). Job states and queue capacity assumptions: [`docs/job-lifecycle.md`](docs/job-lifecycle.md).

The map basemap is chosen with `NEXT_PUBLIC_BASEMAP_PROVIDER` = `none` (default; no basemap, no third-party requests) | `osm` (opt-in, local development only, refused in production builds) | `xyz` (explicit; your own https tile URL + attribution). Tile requests reveal the viewed map area to the provider (never the AOI geometry); `none` makes no third-party requests (ADR-0012/0013).

## Key documents

| Document | Purpose |
|---|---|
| [MASTER_SPEC.md](MASTER_SPEC.md) | Full specification |
| [CLAUDE.md](CLAUDE.md) | Operating rules for AI-assisted work |
| [TASKS.md](TASKS.md) | Phased roadmap and open questions |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/scientific-constraints.md](docs/scientific-constraints.md) | Mandatory scientific rules |
| [docs/dependency-strategy.md](docs/dependency-strategy.md) | Open-source reuse and licensing |
| [docs/data-sources.md](docs/data-sources.md) | Candidate data sources |
| [docs/acceptance-criteria.md](docs/acceptance-criteria.md) | Per-phase acceptance |
| [docs/risk-register.md](docs/risk-register.md) | Risks and mitigations |
| [docs/adr/](docs/adr/README.md) | Accepted decisions (ADR-0001…0013) |
| [docs/phase-1-plan.md](docs/phase-1-plan.md) | Phase 1 plan |
| [docs/phase-reports/phase-1.md](docs/phase-reports/phase-1.md) | Phase 1 evidence and deviations |
| [docs/phase-reports/phase-1-closeout.md](docs/phase-reports/phase-1-closeout.md) | Phase 1 closeout: accepted, open risks, deferred |
| [docs/phase-2-plan.md](docs/phase-2-plan.md) / [phase-2.md](docs/phase-reports/phase-2.md) | Phase 2 plan and evidence |
| [docs/job-lifecycle.md](docs/job-lifecycle.md) | Job states, guarantees, provisional capacity |
| [docs/phase-3-plan.md](docs/phase-3-plan.md) | **Proposed** Phase 3 plan (not started) |
| [docs/third-party-licences.md](docs/third-party-licences.md) | Dependency licence register |

## Licence

**Private repository, all rights reserved.** No open-source licence is chosen (see [`LICENSE`](LICENSE), [ADR-0001](docs/adr/0001-private-repository.md), [ADR-0002](docs/adr/0002-licence-deferred-rights-reserved.md)).

## Scope decisions in force (V1)

| Area | Decision | ADR |
|---|---|---|
| Gold model (Phase 5) | Orogenic gold only | [0003](docs/adr/0003-orogenic-gold-initial-model.md) |
| Earth Engine | Optional, off by default, experimental/non-commercial only | [0004](docs/adr/0004-earth-engine-experimental-noncommercial.md) |
| Authentication | None — **local/private use only; never expose publicly** | [0005](docs/adr/0005-no-authentication-v1.md) |
| Storage | Local filesystem | [0006](docs/adr/0006-local-storage-no-minio.md) |
| Queue | PostgreSQL-backed (`JobQueue` interface) | [0007](docs/adr/0007-postgres-backed-job-queue.md) |
| Limits | AOI ≤ 25 km², ≤ 20 scenes, 30 min jobs (unmeasured starting values) | [0008](docs/adr/0008-conservative-mvp-aoi-limits.md) |
| Science language | Strict naming; confidence + uncertainty mandatory; nothing "confirmed" without field validation | [0009](docs/adr/0009-scientific-naming-confidence-uncertainty.md), [0010](docs/adr/0010-no-confirmed-claims-without-field-validation.md) |

Phase 1 plan: [`docs/phase-1-plan.md`](docs/phase-1-plan.md); evidence: [`docs/phase-reports/phase-1.md`](docs/phase-reports/phase-1.md).
