# Data Model: Project, AOI, Jobs, Outputs

Status: **current for Phase 2.5**. Items marked *(planned)* do not exist yet and are listed so later phases fit without restructuring. Nothing here is scientific content: these entities are bookkeeping.

```
project 1 ──── * aoi                       (exists)
project 1 ──── * job            (planned)  one job belongs to one project
aoi     1 ──── * job            (planned)  a job analyses at most one AOI (nullable for AOI-less jobs such as noop)
job     1 ──── * result         (table exists; unused until an engine runs)
job     1 ──── 1 provenance     (table exists; unused until an engine runs)
result  → files under project/aoi/job path in StorageBackend      (planned layout below)
```

## 1. Entities (as built)
| Entity | Key fields | Rules |
|---|---|---|
| `project` | `id`, `name` (1–120), `description` (≤ 500), `created_at` | Owns AOIs. `MAX_PROJECTS` (default 20). No owner/user (no auth in V1). |
| `aoi` | `id`, `project_id` (NOT NULL), `name`, `geom` Polygon 4326, `source` (input method), `area_km2`, `vertex_count`, `working_crs`, `details`, `created_at` | Belongs to exactly one project. Geometry validated server-side (ADR-0008/0012). `MAX_STORED_AOIS` (default 100) is global. |
| `job` | `id`, `type`, `status`, lease fields, `payload`, `aoi_id`, `project_id`, … | Migration 0004 (Phase 3a, ADR-0014 §7.1): `aoi_id`/`project_id` are both set or both NULL; every non-`noop` job is AOI-bound; a composite FK `(aoi_id, project_id) → aoi(id, project_id)` (RESTRICT) forces the job's project to equal its AOI's project; the project is *derived* from the AOI on enqueue, never client-supplied. `noop` jobs keep NULLs. The API creates `noop` jobs and, in `CONNECTOR_MODE=fixture` only, `catalog_search` jobs bound to an AOI (Phase 3a CP4; `docs/connectors.md`). See `docs/job-lifecycle.md`. |
| `data_asset` | `id`, `project_id`, `aoi_id` (both NOT NULL), `job_id` (optional), `kind`, `storage_key` (unique, immutable), `media_type`, `size_bytes`, `sha256`, `request_hash`, `provenance_id` (NOT NULL, unique) | Staged *input* (catalogue metadata, DEM clip, user vector), never a result: no confidence/score/interpretation. Composite FKs force its project to equal its AOI's project and, if linked, its job's AOI/project. Idempotency: unique `(job_id, kind, request_hash)` for job-bound assets. Migration 0005 (Phase 3a CP3). |
| `storage_tombstone` | `storage_key` (PK), `attempts`, `last_error` | Files whose rows were deleted, awaiting post-commit removal. |
| `result`, `provenance` | `job_id` FK | Reserved for engines; empty. Every future result must satisfy the mandatory envelope (ADR-0009). **Decided 2026-10-05 (owner, option A; implemented with migration 0005, not yet):** `provenance.job_id` becomes nullable while `result.job_id` stays required. `result` rows remain scientific-result records and always need a job; staged input assets (`data_asset`, ADR-0014) may carry provenance without a job link where the model allows it. This relaxes no rule about scientific results (envelope, confidence, uncertainty, sources). |

## 2. Ownership and deletion
- A project **owns** its AOIs. Deleting an AOI never deletes the project.
- Deleting a project with AOIs is refused (409 `project_not_empty`) unless the caller passes `delete_aois=true`; the database FK is `RESTRICT`, so no path removes AOIs implicitly.
- **Jobs (implemented, Phase 3a CP2, ADR-0014 §7.5 r5, `apps/backend/src/app/deletion.py`):** queued or running jobs always block deletion of their AOI/project (409 `has_active_jobs`, also with the cascade flag). Finished jobs need the explicit flag (`delete_aois=true` for a project, `delete_dependents=true` for an AOI; otherwise 409 `needs_cascade`/`project_not_empty`) and are then deleted with the AOI by their exact locked id set. Every deletion is one transaction in the global lock order, restarted as a whole within one attempt budget (3), and answers 503 `retry_later` / 409 `still_referenced` / 500 `integrity_error` as documented in ADR-0014 §7.6.
- **Staged assets (implemented, CP3):** the same transaction deletes the AOI's assets and their provenance, writing tombstones for their files; files are removed after the commit and a failed cleanup never fails the deletion (the routes keep 204). **Results are scientific records:** if any `result` row, or any `provenance` row **not owned by an asset of the AOI(s) selected for deletion**, references the jobs being deleted, the deletion is refused with 409 `has_results`, whatever the cascade flag says (each row counted once; provenance of a selected asset is deleted explicitly with it and is not counted). Order of refusals: `has_active_jobs` → `has_results` → `needs_cascade`/`project_not_empty`. Since migration 0006 (owner option B, 2026-10-06) `result.job_id` and `provenance.job_id` are `ON DELETE RESTRICT`, so raw SQL cannot silently remove those records with a job; this is a second line behind the guard, not a replacement (`docs/phase-reports/migration-0006-design-note.md`; `TRUNCATE … CASCADE` is outside it).

## 3. How future jobs and outputs attach *(planned, to be fixed by the phase that adds the first engine job)*
1. Add `job.project_id uuid NOT NULL REFERENCES project(id) ON DELETE RESTRICT` and `job.aoi_id uuid NULL REFERENCES aoi(id) ON DELETE RESTRICT` (migration `0004` or later). `noop` jobs may keep `aoi_id` null.
2. A job's payload references an AOI **by id** and stores a snapshot hash of the AOI geometry in provenance (`aoi_hash`), so a result remains interpretable if the AOI is later removed or replaced.
3. Output files use logical storage keys (ADR-0006): `projects/<project_id>/aois/<aoi_id>/jobs/<job_id>/<artifact>` (COG rasters, vector exports). Keys are derived from ids only, never from user text.
4. Each engine output is a `result` row whose `envelope` satisfies the mandatory result envelope (confidence, uncertainty, explanation, sources, provenance, `validation_status = unvalidated`, …). The API must refuse to serve results without it.
5. Limits (ADR-0008) are checked at job creation against the referenced AOI; the AOI's own limits were checked when it was saved.

## 4. What is deliberately not modelled yet
Users/owners, sharing, per-project settings or quotas, project rename, tags, AOI versioning, job↔AOI history, output retention policy.
