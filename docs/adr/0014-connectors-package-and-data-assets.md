# ADR-0014: Connectors package, `data_asset` entity and job↔project/AOI linkage (Phase 3)

- **Status:** **PROPOSED — awaiting owner approval. Not implemented.**
- **Date:** 2026-10-04
- **Proposed by:** Claude, per `docs/phase-3-plan.md`

## Context
Phase 3 stages data inputs (catalogue metadata, clipped DEM, user-supplied vectors). That needs somewhere for connector code to live that respects ADR-0011 (`geo_common` stays free of domain logic and the backend never imports worker code), a place to record staged data that is *not* a scientific result, and the job↔project/AOI attachment already described in `docs/data-model.md`.

## Decision (proposed)
1. **`workers/connectors/` (`geo_connectors`)** holds connector implementations, the budgeted HTTP client, the cache and the provenance helper. It imports `geo_common`; `apps/backend` must not import it (a test enforces this); `workers/runner` registers its handlers by import path. Connectors perform data access only — no interpretation, scoring or analysis.
2. **`data_asset`** (migration 0005): `id, project_id, aoi_id, job_id NULL, kind ∈ {scene_catalog, dem_clip, user_vector}, storage_key, media_type, size_bytes, sha256, provenance_id, created_at`. Assets are **inputs**, not `result`s: they carry no confidence/score/interpretation and are never described as findings.
3. **`job.project_id` / `job.aoi_id`** (migration 0004): nullable FKs `ON DELETE RESTRICT`, with a `CHECK` that every non-`noop` job has both. `project_id` is derived from the AOI on the server.
4. **Deletion:** removing an AOI/project that has assets needs the explicit cascade flag and also deletes the stored files; a project/AOI with a `queued` or `running` job cannot be deleted (409).
5. **Modes:** `CONNECTOR_MODE ∈ {disabled (default), fixture, live}`; `live` needs explicit opt-in and `ENABLED_CONNECTORS`. Earth Engine is gated separately by ADR-0004 and its owner-validation condition; it is not a mode.
6. **Egress safety:** connector URLs are built from fixed provider bases only; redirects/pagination links must stay on the allow-listed host; responses are size-capped and content-type-checked.

## Consequences
- New dependencies in `geo_connectors` only (`httpx`, `rasterio`), recorded in the licence register; no `pystac-client`.
- The `Job` contract and Compose gain a worker that needs outbound network access when `live`; the backend still needs none.
- If rejected or amended, Phase 3 slice 3a is re-planned before any code is written.

## Revisit when
A second worker image is needed for heavy tools (MintPy, pyGIMLi), connectors need credentials (new ADR for secret handling), or assets need retention/purge policies.
