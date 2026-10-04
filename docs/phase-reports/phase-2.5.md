# Phase 2.5 Report — Structural Hardening (project entity, basemap abstraction)

Status: **approved by the owner with two required follow-ups, now implemented** (§6). Phase 3 has **not** been started; its plan is `docs/phase-3-plan.md` (proposal only).
Scope statement: **no analysis, scoring, Earth Engine, 3D or auth expansion.** Only bookkeeping (projects), AOI ownership, and a configuration abstraction.
Decisions: ADR-0013 · Relationships: `docs/data-model.md`.

## 1. What changed
| Item | Delivered |
|---|---|
| 1. Minimal `project` entity | Table `project` (`id`, `name` 1–120, `description` ≤ 500, `created_at`); `MAX_PROJECTS` (default 20) |
| 2. AOIs belong to projects | `aoi.project_id NOT NULL`, FK `ON DELETE RESTRICT`; migration `0003` moves existing AOIs into a "Default project" (none created when there are no AOIs) |
| 3. Contracts / persistence / API | `Project`, `ProjectCreateRequest`, `ProjectList` in `packages/schemas`; `Aoi`/`AoiSummary` carry `project_id`; `POST/GET /projects`, `GET/DELETE /projects/{id}`; saving an AOI (JSON or upload) requires `project_id`; `GET /aois?project_id=` |
| 4. Smallest project-aware UI | `ProjectBar` (select / create / delete); AOI list and Save are scoped to the selected project; Save disabled with an explanation when none exists |
| 5. Basemap provider abstraction | `lib/basemap.ts`: `osm` (default, dev-only) · `xyz` (https URL + mandatory attribution) · `none`; invalid config → `none` + visible warning; UI shows provider and the privacy note; Docker build args added |
| 6. Documentation | ADR-0013, `docs/data-model.md` (project ↔ AOI ↔ future jobs ↔ outputs, deletion rules, planned attachment), architecture §2b |

**Unchanged by design:** all AOI validation and upload hardening. The existing AOI/parser test suites were not weakened (only fixtures gained a project); a test confirms an over-limit AOI and a hostile upload are still rejected when a valid project is supplied.

## 2. Verification performed
| Check | Result |
|---|---|
| `make ci` | exit 0 — ruff, mypy (35 files), 170 unit + 123 PostGIS-backed tests, 25 guards, licence register, frontend lint/types/format/**53** tests/build, schema drift |
| Migration `0003` | up/down/up; backfill of pre-existing AOIs into "Default project" (tested by downgrading to `0002`, inserting AOIs, upgrading); no project invented when empty; DB-level NOT NULL, FK, RESTRICT and name constraints |
| Project API | CRUD, validation, limit (409, race-safe under 12 concurrent creates), ownership counts, filtering, upload requires/uses project, preview needs none, delete refuses non-empty unless `delete_aois=true`, deleting an AOI keeps the project |
| Real browser (headless Chromium, real backend + PostGIS, `provider=none`) | no-project state; validate without project; create project; save circle; upload GeoJSON; hostile KML still rejected; second project isolated; switch/reload; delete one AOI; delete non-empty project with explicit "AND its 2 AOI(s)" confirmation |
| Docker (`make up`, fresh build) | migration at `0003`; project rules via curl; CORS preflight for DELETE → 200; ports on `127.0.0.1`; no Redis/MinIO |

### Defect found by the browser check — it also affected accepted Phase 2
**Deleting an AOI (and a project) failed in a real browser** with "Cannot reach the backend": CORS allowed only `GET, POST`, so the `DELETE` preflight was rejected. Unit tests mock `fetch`, and the Phase 2 browser check never clicked delete, so Phase 2's "delete" worked via curl/tests but not in the UI. Fixed (`allow_methods` now includes `DELETE`; PUT/PATCH remain refused) with a regression test on the preflight. Phase 2's report is amended accordingly.

## 3. Not verified / limitations
- GitHub Actions for the Phase 2.5 commits: see the hand-over message for the last observed status.
- The browser checks are ad-hoc scripts, **not in CI** — which is why the DELETE/CORS defect and the earlier MapLibre-worker defect escaped unit tests. A committed browser smoke test is a recommended follow-up (deferred; needs Chromium in CI).
- OSM basemap tiles were still not exercised (checks ran with `provider=none`); `xyz` with a real server untested beyond unit tests of config validation.
- Basemap env change: `NEXT_PUBLIC_BASEMAP_TILE_URL` alone no longer selects a provider; set `NEXT_PUBLIC_BASEMAP_PROVIDER=xyz`. Existing `.env` files with only a tile URL fall back to `osm`.
- No project rename (`PATCH`), no per-project quotas (`MAX_STORED_AOIS` is global), no owner/permissions.
- `job` has **no** `project_id` yet: the attachment is documented, not built (by design; added with the first real job type).
- Real-world AOI files and OSM policy remain open from Phase 2 (risks P-9, P-10).

## 4. Acceptance checklist (tick when you accept)
- [ ] 1. A `project` entity exists with name/description and a bounded count (`MAX_PROJECTS`).
- [ ] 2. Every AOI belongs to exactly one project; existing AOIs were migrated, not lost.
- [ ] 3. API/contracts/persistence updated; saving requires a project; preview does not.
- [ ] 4. The UI offers the smallest project flow (select / create / delete) and scopes AOIs to the selected project.
- [ ] 5. Basemap is configured through a provider abstraction with `osm` / `xyz` / `none`, validated, with the privacy note shown.
- [ ] 6. `docs/data-model.md` and ADR-0013 describe project ↔ AOI ↔ future jobs ↔ outputs and deletion rules.
- [ ] 7. AOI validation and upload hardening behave exactly as before (tests unchanged in substance).
- [ ] 8. No analysis, scoring, Earth Engine, 3D or auth expansion was added.
- [ ] 9. `make ci` green locally and the GitHub Actions run green on the final commit.
- [ ] 10. Owner decisions below are given.

## 5. Decisions for the owner
1. Accept Phase 2.5 (checklist above) so Phase 3 may be planned.
2. Do you want a committed browser smoke test in CI before Phase 3? (My recommendation: yes — two real defects were found only in a browser.)
3. Keep `osm` as the default basemap for development, or default to `none` until a provider is chosen?
4. Phase 5 remains gated on the target region/pilot area; Earth Engine on the owner's commercial-eligibility validation.

## 6. Required follow-ups (owner approval, before Phase 3)
| Follow-up | Delivered |
|---|---|
| 1. Browser smoke test in CI | `apps/frontend/e2e/smoke.e2e.ts` (Playwright, real Chromium → Next.js → FastAPI → PostGIS) and CI job `e2e`. One flow, as steps: **connectivity** (cross-origin readiness + limits + MapLibre canvas), **create project**, **create AOI**, **delete AOI**, **delete project with explicit cascade confirmation** (declining changes nothing; accepting removes project and AOIs, verified through the API), and **no uncaught page errors / console errors** (covers "Worker failed to load" and CORS blocks). `retries: 0`. `make e2e`, `make ci-full`; guard test keeps the CI job from being removed. |
| 2. Default basemap `none` | Default is `none` everywhere (code, `.env.example`, Compose, Dockerfile, Settings). `osm` is opt-in, honoured only outside production builds, **refused in the Docker image with a visible warning**. `xyz` needs explicit provider + https URL + attribution (a tile URL alone is ignored). Invalid config still warns and falls back. |
| CORS future-safety (extra) | Allowed methods are now **derived from the OpenAPI operations** (restricted to `GET, HEAD, POST, PUT, PATCH, DELETE`), so a new verb cannot silently break browsers. Headers limited to `Content-Type`, `X-Request-ID`; credentials off; preflight cached 600 s. Tests: every declared operation passes a preflight; unused/exotic verbs and unlisted origins are refused; derivation works with lazily-included routers; no endpoint may be hidden from the schema. |

### Verification of the follow-ups
- `make ci` exit 0 (183 unit + 123 PostGIS tests, 27 guards, 58 frontend tests, build, schema drift, licence register).
- `make e2e` passes locally (headless Chromium, ~13 s warm).
- **Mutation check:** removing `DELETE` from the CORS policy made the smoke test fail at the "delete AOI" step; restored afterwards.
- The same smoke test also **passed against the real Docker Compose stack** (built images, `next start` standalone server), not only against dev servers.
- Production image with `NEXT_PUBLIC_BASEMAP_PROVIDER=osm`: UI shows "No basemap" plus the development-only warning; **zero third-party requests** observed.
- GitHub Actions: the `e2e` job ran green on run #7 (see 9d). Locally the preinstalled Chromium is used via `E2E_CHROMIUM_PATH` because Playwright's own browser is not installed in this sandbox.

### Updated acceptance items
- [x] 9a. Browser smoke test exists in CI and passes locally and against Compose.
- [x] 9b. Basemap default is `none`; `osm` opt-in/dev-only; `xyz` explicit with attribution; warnings preserved.
- [x] 9c. CORS policy derived from declared operations and tested for every operation.
- [x] 9d. GitHub Actions run #7 (commit `02b6b05`) concluded `success` with all six jobs green, **including the new `e2e` job** (`npx playwright install --with-deps chromium` + smoke test passed on the GitHub runner, ~23 s). Later commits (`9a7947e`, docs-only) were still queued when this was written.
