# ADR-0008: Conservative MVP AOI and compute limits

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 8)

## Context
V1 runs on local/dev hardware of unknown size. Unbounded AOIs or archives would exhaust CPU, RAM, disk and external quotas.

## Decision
Default limits (all configurable by environment variable, **enforced server-side at AOI creation and job creation**, never only in the UI):

| Setting | Default | Rationale |
|---|---|---|
| `MAX_AOI_AREA_KM2` | 25 | ~5 × 5 km; small enough for local processing |
| `MAX_RADIUS_KM` | 2.5 | circle of ≈19.6 km², inside the area limit |
| `MIN_AOI_AREA_KM2` | 0.01 | ≈ one 100 m × 100 m Landsat thermal pixel; smaller AOIs give meaningless thermal results |
| `MAX_AOI_VERTICES` | 2000 | bounds geometry-processing cost |
| `MAX_UPLOAD_MB` | 10 | |
| `MAX_ARCHIVE_UNCOMPRESSED_MB` | 50 | zip-bomb guard (KMZ / zipped Shapefile) |
| `MAX_ARCHIVE_FILES` | 50 | zip-bomb guard |
| `MAX_TIME_WINDOW_DAYS` | 365 | enough to span seasons for thermal persistence |
| `MAX_SCENES_PER_JOB` | 20 | primary compute bound for EO pipelines |
| `JOB_TIMEOUT_SECONDS` | 1800 | hard kill |
| `WORKER_CONCURRENCY` | 1 | |
| `MAX_QUEUED_JOBS` | 10 | |

**These numbers are starting guesses (confidence: *guess*), not measured.** They must be re-evaluated after Phase 3–4 profiling on the reference machine, and changed only via a documented update to this ADR.

## Consequences
- Requests exceeding limits are rejected with a specific error stating the limit and value.
- Larger AOIs must be tiled by the user in V1; no automatic tiling.
- Acceptance tests for Phase 2 include boundary values for each limit.
- A limit increase never silently changes scientific behaviour; engine docs state validity ranges separately.

## Revisit when
Profiling data exists, or the owner defines reference hardware.
