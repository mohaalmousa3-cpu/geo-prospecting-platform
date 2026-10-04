# ADR-0011: Shared Python package `packages/pycommon` (`geo_common`)

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (approval of T8)

## Context
Workers must not import backend code, yet backend and workers both need the job queue, storage abstraction, configuration and generated schema models. `packages/schemas` holds language-neutral contracts only.

## Decision
Create `packages/pycommon`, importable as `geo_common`. It may contain **only**:
- shared contracts and generated Pydantic models from `packages/schemas`;
- queue abstraction (`JobQueue`) and its PostgreSQL implementation;
- storage abstraction (`StorageBackend`) and its local implementation;
- shared configuration (`Settings`);
- generic utilities (logging setup, DB engine factory, envelope serialisation guard).

It MUST NOT contain analysis-specific business logic: no scoring, indices, thermal/gold/void/geophysics algorithms, no connectors, no scientific thresholds or weights. Engine code lives in `workers/<engine>`; API code in `apps/backend`.

Dependency direction: `apps/backend → geo_common ← workers/*`. `geo_common` imports neither. A test enforces this.

## Consequences
- One place for queue/storage/envelope semantics; no duplicated, divergent copies.
- Risk of the package becoming a dumping ground: reviews must reject domain logic here (CLAUDE.md §6 updated).
- Extends the directory layout in `docs/architecture.md`; `workers/runner` hosts the generic worker loop.
