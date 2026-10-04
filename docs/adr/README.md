# Architecture Decision Records

One file per decision: `NNNN-title.md` with Status, Context, Decision, Consequences. Changes to an accepted ADR require a new ADR that supersedes it.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-private-repository.md) | Repository stays private | Accepted |
| [0002](0002-licence-deferred-rights-reserved.md) | No open-source licence yet; rights reserved | Accepted |
| [0003](0003-orogenic-gold-initial-model.md) | Phase 5 gold model = orogenic gold only | Accepted |
| [0004](0004-earth-engine-experimental-noncommercial.md) | Earth Engine: experimental / non-commercial, optional, replaceable, off by default; owner must validate commercial eligibility before operational use | Accepted (amended) |
| [0005](0005-no-authentication-v1.md) | No authentication in V1; local/private only | Accepted |
| [0006](0006-local-storage-no-minio.md) | Local filesystem storage; no MinIO | Accepted |
| [0007](0007-postgres-backed-job-queue.md) | PostgreSQL-backed job queue; no Redis in V1 | Accepted |
| [0008](0008-conservative-mvp-aoi-limits.md) | Conservative MVP AOI/compute limits | Accepted |
| [0009](0009-scientific-naming-confidence-uncertainty.md) | Strict naming; mandatory confidence/uncertainty | Accepted |
| [0010](0010-no-confirmed-claims-without-field-validation.md) | No "confirmed" language without field validation | Accepted (amended: geophysics ⇒ at most high-confidence investigation priority) |
| [0011](0011-shared-python-package-pycommon.md) | Shared package `packages/pycommon` (contracts/abstractions/utilities only) | Accepted |
| [0012](0012-aoi-input-and-validation.md) | AOI input, validation and basemap handling (Phase 2) | Accepted within approved Phase 2 scope |

## Still undecided (no ADR yet)
Deployment target, target region(s)/pilot area (required before Phase 5 design — ADR-0003 amendment), reference hardware.
