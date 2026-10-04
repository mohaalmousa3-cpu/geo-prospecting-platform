# ADR-0013: Minimal `project` entity and basemap provider abstraction (Phase 2.5)

- **Status:** Accepted within the Phase 2.5 scope approved by the owner (2026-10-04)
- **Date:** 2026-10-04
- **Decided by:** Owner (scope), Claude (design)

## Context
Before any analysis exists, jobs and outputs need a stable owner. Without a container, future jobs would hang off bare AOIs, and AOIs could not be grouped. Separately, the map hard-coded one tile server configuration, although the basemap provider is an open decision with privacy and terms-of-use consequences (ADR-0012 §11).

## Decision
1. **`project`** is a named container: `id`, `name` (1–120), `description` (≤ 500, nullable), `created_at`. Bookkeeping only — no scientific fields, no owner/user (ADR-0005: no auth).
2. **Every AOI belongs to exactly one project** (`aoi.project_id NOT NULL`, FK `ON DELETE RESTRICT`). Migration `0003` moves pre-existing AOIs into a "Default project" (none is created if there are no AOIs).
3. **API:** `POST/GET /projects`, `GET/DELETE /projects/{id}`. Saving an AOI (`POST /aois`, `POST /aois/upload`) requires `project_id` (422 `project_required`, 404 `project_not_found`); **preview needs none**. `GET /aois?project_id=` filters. Responses include `project_id`; projects include `aoi_count`.
4. **Deletion is explicit:** deleting a project that still has AOIs returns 409 `project_not_empty` unless `?delete_aois=true`. Deleting an AOI never deletes its project. The database FK is `RESTRICT`, so only the API's explicit cascade can remove AOIs.
5. **Limits:** `MAX_PROJECTS` (default 20) in addition to the global `MAX_STORED_AOIS` (still global, not per project). Provisional operational safeguards like the other ADR-0008 limits.
6. **No `PATCH` (rename), no project-level settings, no per-project permissions** — deferred.
7. **Future jobs and outputs** will reference a project (and usually an AOI); see `docs/data-model.md`. **Nothing in this ADR adds `project_id` to `job`**: that happens in the phase that creates the first real job type, together with its output layout.
8. **Basemap provider abstraction** (`apps/frontend/src/lib/basemap.ts`): `NEXT_PUBLIC_BASEMAP_PROVIDER` ∈ `osm` (default; development use only) | `xyz` (own https tile URL + mandatory attribution; `http` only for localhost) | `none` (no third-party requests). Invalid configuration falls back to `none` with a visible warning. The map reads only the resolved `Basemap`; the UI states the provider and that tile requests reveal the viewed area (not the AOI). The previous `NEXT_PUBLIC_BASEMAP_TILE_URL` alone no longer selects a provider; set `…_PROVIDER=xyz`.

## Amendment (2026-10-04, Phase 2.5 follow-ups required by the owner)
- **Default basemap provider is `none`** (unset/empty → no basemap, no third-party requests, no warning). `NEXT_PUBLIC_BASEMAP_PROVIDER=osm` is **opt-in and for local development only**: it is honoured by `next dev` and tests but **refused in production builds** (including the Docker image) with a visible warning and fallback to `none`.
- **`xyz` requires explicit provider selection** (a tile URL alone is ignored), an https `{z}/{x}/{y}` URL (http only for localhost) and a non-empty attribution.
- Invalid configuration keeps the visible-warning + `none` fallback behaviour. Supersedes the "default `osm`" statement in §8 and ADR-0012 §11.
- **CORS is derived, not hand-listed.** Allowed methods = the HTTP methods of the operations in the app's OpenAPI document, restricted to `GET, HEAD, POST, PUT, PATCH, DELETE`; `OPTIONS`, `TRACE`, `CONNECT` and verbs without an endpoint are never allowed. Allowed request headers are `Content-Type` and `X-Request-ID` only (no `Authorization`: no auth in V1); credentials are off; preflight is cacheable for 600 s. A new `PATCH` endpoint therefore needs no CORS edit, and tests assert every declared operation passes a browser preflight. Endpoints must not be hidden from the OpenAPI schema (enforced by a test), because the schema is the source.
- **A browser smoke test is part of CI** (`e2e` job, Playwright): connectivity, create project, create AOI, delete AOI, delete project with explicit cascade confirmation, no uncaught page/console errors.

## Consequences
- AOI creation clients must send `project_id` (the frontend now has a project selector; the API is otherwise unchanged and **all AOI validation and upload hardening behaviour is unchanged**).
- Adding a basemap provider is a code change in one function plus a test; secrets-bearing providers (API keys) are out of scope and would need a new ADR because `NEXT_PUBLIC_*` values are public.
- A single global storage cap means one project can consume the whole AOI budget; acceptable for local/private V1.

## Revisit when
Jobs/outputs are introduced (add `job.project_id`), rename/permissions are needed, a keyed basemap provider is wanted, or per-project quotas matter.
