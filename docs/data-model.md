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
| `job` | `id`, `type`, `status`, lease fields, `payload`, … | Only `noop` exists. **Has no `project_id` yet.** See `docs/job-lifecycle.md`. |
| `result`, `provenance` | `job_id` FK | Reserved for engines; empty. Every future result must satisfy the mandatory envelope (ADR-0009). |

## 2. Ownership and deletion
- A project **owns** its AOIs. Deleting an AOI never deletes the project.
- Deleting a project with AOIs is refused (409 `project_not_empty`) unless the caller passes `delete_aois=true`; the database FK is `RESTRICT`, so no path removes AOIs implicitly.
- *(planned)* Once jobs exist, deleting an AOI or project with jobs/outputs must be refused or explicitly cascade to jobs, results, provenance **and stored files** in one documented step. Results are scientific records: the default will be refuse, not cascade.
- Running jobs must block deletion of their project/AOI (to be enforced when `job.project_id` is added).

## 3. How future jobs and outputs attach *(planned, to be fixed by the phase that adds the first engine job)*
1. Add `job.project_id uuid NOT NULL REFERENCES project(id) ON DELETE RESTRICT` and `job.aoi_id uuid NULL REFERENCES aoi(id) ON DELETE RESTRICT` (migration `0004` or later). `noop` jobs may keep `aoi_id` null.
2. A job's payload references an AOI **by id** and stores a snapshot hash of the AOI geometry in provenance (`aoi_hash`), so a result remains interpretable if the AOI is later removed or replaced.
3. Output files use logical storage keys (ADR-0006): `projects/<project_id>/aois/<aoi_id>/jobs/<job_id>/<artifact>` (COG rasters, vector exports). Keys are derived from ids only, never from user text.
4. Each engine output is a `result` row whose `envelope` satisfies the mandatory result envelope (confidence, uncertainty, explanation, sources, provenance, `validation_status = unvalidated`, …). The API must refuse to serve results without it.
5. Limits (ADR-0008) are checked at job creation against the referenced AOI; the AOI's own limits were checked when it was saved.

## 4. What is deliberately not modelled yet
Users/owners, sharing, per-project settings or quotas, project rename, tags, AOI versioning, job↔AOI history, output retention policy.
