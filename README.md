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

Next.js · FastAPI · PostgreSQL/PostGIS · Redis + background workers · Docker Compose · MapLibre · CesiumJS.
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

## Licence

Not yet chosen — see [`LICENSE`](LICENSE) for guidance. Decision is tracked as Open Question #1 and is constrained by dependency licences.
