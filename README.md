# geo-prospecting-platform

A scientific web platform for **prospectivity and anomaly screening** from remote-sensing, geological, terrain and thermal data — for gold-related targets, cavity/void-related targets and thermal anomalies — with explicit confidence and uncertainty.

> **Status: Phase 0 — foundation only.** No application code or scientific engines exist yet. This repository currently contains governance, specification and scaffolding.

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
  thermal/ gold_prospectivity/ void_evidence/ geophysics/ insar/
packages/
  schemas/         Shared JSON Schema / OpenAPI contracts (source of truth)
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
| [docs/adr/](docs/adr/README.md) | Accepted decisions (ADR-0001…0010) |
| [docs/phase-1-plan.md](docs/phase-1-plan.md) | Actionable Phase 1 plan |

## Licence

**Private repository, all rights reserved.** No open-source licence is chosen (see [`LICENSE`](LICENSE), [ADR-0001](docs/adr/0001-private-repository.md), [ADR-0002](docs/adr/0002-licence-deferred-rights-reserved.md)).

## Scope decisions in force (V1)

| Area | Decision | ADR |
|---|---|---|
| Gold model (Phase 5) | Orogenic gold only | [0003](docs/adr/0003-orogenic-gold-initial-model.md) |
| Earth Engine | Optional, off by default, experimental/non-commercial only | [0004](docs/adr/0004-earth-engine-experimental-noncommercial.md) |
| Authentication | None — **local/private use only; never expose publicly** | [0005](docs/adr/0005-no-authentication-v1.md) |
| Storage | Local filesystem | [0006](docs/adr/0006-local-storage-no-minio.md) |
| Queue | PostgreSQL-backed | [0007](docs/adr/0007-postgres-backed-job-queue.md) |
| Limits | AOI ≤ 25 km², ≤ 20 scenes, 30 min jobs (unmeasured starting values) | [0008](docs/adr/0008-conservative-mvp-aoi-limits.md) |
| Science language | Strict naming; confidence + uncertainty mandatory; nothing "confirmed" without field validation | [0009](docs/adr/0009-scientific-naming-confidence-uncertainty.md), [0010](docs/adr/0010-no-confirmed-claims-without-field-validation.md) |

Next step: [`docs/phase-1-plan.md`](docs/phase-1-plan.md) (awaiting approval; no application code exists yet).
