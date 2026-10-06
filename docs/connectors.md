# Connectors (Phase 3a — fixtures only)

> **Status (CP4, 2026-10-06; implemented; Phase 3a ACCEPTED by the owner as fixtures-only on 2026-10-06 at `0c2406f`, CI run #21).** This is not live-slice readiness. There is no live provider, no HTTP client, no cache, no `rasterio` and no network code in this repository; nothing here was verified against a real catalogue. F-1 stays open under the fixtures-only exception; D8 live-verification readiness is pending; no host, port or egress control is approved. Binding decisions: ADR-0014, ADR-0008, ADR-0011.

## 1. What exists

A `catalog_search` job reads a **committed synthetic fixture** and stores the matching catalogue entries as one `scene_catalog` data asset (a JSON file) with provenance. The asset is an **input** to later phases: catalogue metadata only, with no confidence, score, uncertainty, interpretation or `result` row. `insufficient_data` here means only *"the catalogue search completed and matched no items for the request"* — a queue status, not a scientific outcome.

| Piece | Where |
|---|---|
| Connector contract (`FetchContext` → `FetchResult`, pure, no I/O), registry, `CONNECTOR_MODE` resolution | `workers/connectors/src/geo_connectors/{contracts,registry,errors}.py` |
| Fixture connector and the two committed synthetic fixtures | `geo_connectors/fixture.py`, `geo_connectors/fixtures/` |
| Job handler (read AOI → fetch → stage file → publish asset) | `geo_connectors/handler.py` |
| Request identity (`request_hash`, version 1) | `geo_connectors/request_hash.py` (definition in the module docstring; golden value pinned by a test) |
| Persistence and storage protocol (shared, no scientific logic) | `packages/pycommon/src/geo_common/assets_pg.py`, `storage.py`, migration `0005_data_asset.py` |
| Public API | `GET /api/v1/connectors` (fixture-only capability; no host or credential), `GET /api/v1/aois/{id}/assets` (AOI-scoped list), `POST /api/v1/jobs` (`apps/backend/src/app/api/jobs.py`, `catalog_jobs.py`); `GET /api/v1/assets…` (read/delete only) |

## 2. `CONNECTOR_MODE`

One setting, read by **both** the API and the worker (each process reads its own environment; keep them equal).

| Mode | API `POST /jobs` with `catalog_search` | Worker running such a job |
|---|---|---|
| `disabled` (default) | **409 `connectors_disabled`**; no job is created | the job fails with "connectors disabled (CONNECTOR_MODE=disabled)"; nothing is written |
| `fixture` | 201, job queued | reads the committed fixture; publishes an asset or ends `insufficient_data` |
| `live` | **501 `connector_live_not_available`**; no job is created | the job fails with "live connector mode is not available in Phase 3a"; nothing is written |

`live` is accepted as a configuration value only so that the refusal is explicit and stable; there is no live code path. `noop` jobs do not depend on the mode.

## 3. Creating a job

```
POST /api/v1/jobs
{"type": "catalog_search", "aoi_id": "<uuid>",
 "payload": {"start": "2026-01-01", "end": "2026-06-30",
             "collections": ["synthetic-optical"], "max_items": 20}}
```

* **The AOI is the only target.** The project is derived from the AOI by the queue layer (`INSERT … SELECT`, ADR-0014 §7.4) and returned as `project_id`; the request has no `project_id` field and any extra key is rejected with 422 (also inside `payload`).
* **Payload keys** (exactly these; all others are refused): `start`, `end` (`YYYY-MM-DD`), `collections` (1–10 names, `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`), optional `max_items`. There is deliberately **no** dataset, fixture, provider, host, URL, cache, DEM or user-vector option: which connector answers is decided only by the server's `CONNECTOR_MODE`.
* **Limits (server-side, never clamped):** `end ≥ start`; window ≤ `MAX_TIME_WINDOW_DAYS`; `max_items` ≤ `MAX_SCENES_PER_JOB` (default made explicit in the stored payload); at most 10 collections (a **temporary fixtures-only operational bound**, confirmed by the owner 2026-10-06; not a provider or API capability; to be revisited before any live catalogue slice). These are provisional operational safeguards, not scientific thresholds (ADR-0008).
* **Stored payload is normalised:** collections sorted and de-duplicated, `max_items` always present.
* **Order of refusals** (no refusal creates a job): 422 `validation_error` (shape, targeting, limits) → mode gate (409 / 501) → 404 `aoi_not_found` → 429 `queue_full` / 503 `retry_later` (queue). The mode gate comes before the AOI lookup, so a disabled or live server never reveals whether an AOI exists.
* `GET /jobs/{id}` returns `aoi_id` and `project_id`; `POST /jobs/{id}/cancel` works as for `noop`.

## 4. Execution (worker)

1. The runner claims the job and starts the registered handler (`geo_connectors.handler:catalog_search`, an import-path string — the runner never imports the connectors) in a child process with the job context.
2. The handler loads the job's AOI, resolves the connector for the mode, and calls `fetch()` — **pure**: no database or storage I/O and no socket inside the fetch window.
3. **Zero records →** the handler returns `insufficient_data` with the explanation "no catalogue items matched the request" (stored in the job's `error` field). No file, no `data_asset`, no `provenance`, no `result` row.
4. Otherwise: a pre-check of `cancel_requested`; a fresh asset id and key (keys are never reused); the file is staged under `.staging/`, flushed and renamed; **one transaction** verifies under locks that the job is running, owned by this worker, in the expected AOI/project and not cancel-requested, then inserts provenance and the asset. The runner completes the job only after the handler returns.
5. If publication is refused or fails, only this worker's own new file is removed (3 bounded attempts); anything that cannot be removed is left for the report-only `make reconcile-assets`.

**Idempotency (`request_hash`).** `UNIQUE (job_id, kind, request_hash)` makes the *publication request* idempotent for one job: a retry of the same job after a lost lease or a worker death finds the existing asset and succeeds without a second row or file. It is **not** result deduplication: the same request in a different job produces a separate asset.

**Provenance** (CLAUDE.md §4.6) per asset: kind, job id, asset id, `request_hash`, and `source` = connector, kind (`fixture`), dataset, dataset version, `retrieved_at` (the fixture's declared generation date, deterministic), parameters, code version, `synthetic: true`.

## 5. Deletion interplay

Deleting an AOI or project removes its assets, their provenance and (after the commit) their files; the routes keep `204`. The refusal order is **`has_active_jobs` → `has_results` → `needs_cascade` / `project_not_empty`** (all 409). `has_results` counts, over the jobs of the AOI(s) being deleted, each `result` row once plus each `provenance` row **not owned by an asset of the AOI(s) selected for deletion**; provenance of a selected asset is deleted explicitly and is not counted. See `docs/data-model.md` §2 and ADR-0014 (CP3/CP4 records). Since migration 0006 (owner option B) `result.job_id` and `provenance.job_id` are `RESTRICT`: a raw `DELETE FROM job` is refused while such rows exist; the application guard still answers first (`docs/phase-reports/migration-0006-design-note.md`). `TRUNCATE … CASCADE` remains an administrative operation outside any protection.

## 6. Worker image

The worker image installs `geo-connectors` from the same lockfile through the Dockerfile build argument `EXTRA_PACKAGE` (set only for the worker in `docker-compose.yml`); it adds **no** third-party package (the connectors depend only on `geo-common`). The backend image does not contain `geo_connectors` or `runner`. `scripts/image_smoke.sh` (CI job *docker build smoke*, or `make image-smoke` with a Docker daemon) verifies inside the built images that the registered handlers load, that the backend image lacks the connectors, and that an API-created job runs in the worker image.

## 7. What is verified, and how (labels)

* **Real** (real HTTP app, PostgreSQL, filesystem, the runner's spawn child): `apps/backend/tests/test_catalog_jobs_api.py` (modes, targeting, payload limits, queue limits), `tests/integration/test_catalog_search_flow.py` (non-empty and zero-result runs, worker-death-after-publication retry, per-job idempotency, worker-side mode mismatch, deletion and report-only reconcile), `workers/connectors/tests/`.
* **Real crash:** a real `os._exit(137)` of the handler process after publication (flow test).
* **Audit, not a firewall:** a `sys.addaudithook` inside the runner's child records socket events while a real job runs; only the test PostgreSQL endpoint is allowed and nothing occurs inside the fetch window (`test_the_runner_child_connects_only_to_the_test_database…`). This is evidence about this code path in this test, not a production egress control.
* **Simulated:** a stub queue raising `QueueBusyError` (503 mapping for `catalog_search`); handler-level storage-fault and cancel-seam tests (`workers/connectors/tests/test_handler.py`).
* **Policy-only:** writer allow-list and status-transition checks (T-D14), the Dockerfile/compose packaging check.
* **Image:** `scripts/image_smoke.sh` (needs Docker; CI job *docker build smoke*).

## 8. Not here (by design)

Live providers and hosts, HTTP client, cache, retries/back-off against a remote, `rasterio`, DEM clips, user vectors, 3D, Earth Engine, any scoring or interpretation, destructive orphan cleanup, UI for jobs/assets. Each needs a separate, explicit instruction (and, for live slices, the owner's approval of exact hosts/ports and of the application and network controls).
