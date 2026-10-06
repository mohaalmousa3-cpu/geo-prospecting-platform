# Phase 3a closure checkpoint — reconciliation and acceptance matrix

> **Acceptance record (2026-10-06).** **Phase 3a is ACCEPTED by the owner as fixtures-only (2026-10-06) at `0c2406fffa7e2332c4665a0fd38f8b829f9d9995` on `claude/phase-3a-fixtures`, with CI run #21 (https://github.com/mohaalmousa3-cpu/geo-prospecting-platform/actions/runs/37479576123).** The acceptance covers only the implemented fixtures-only scope and the evidence reported for that SHA; it is not authorisation for Phase 3b, any live connector or any networked provider execution, and it does not waive F-1 for any live work. T-D11 and T-D15 remain simulated; T-D14, T8 and the policy portions of T5/T9 remain policy-only; network audit/hook tests are test controls, not an egress firewall; nothing here implies live-provider readiness or a verified live network control. Remaining live requirements are **deferred**: F-1 closed, D8 readiness R1–R8, owner approval of exact hosts/ports and of application and network controls, HTTP-client selection (ADR-0014 §9/§10), a revisit of the 10-collection cap, and a new start instruction.
>
> *Status when the closure checkpoint was reported (historical):* implemented, awaiting the owner's review. Scope: fixtures-only (ADR-0014). No live provider, host, HTTP client, cache, `rasterio`, DEM, `user_vector`, 3D, UI feature or new dependency exists. F-1 remains open under the fixtures-only exception; D8 live-verification readiness is pending; no host or network control is approved. The commit SHA and CI result of this checkpoint are reported with the checkpoint, not stored here.

## 1. What the closure checkpoint added
| Item | Where |
|---|---|
| Migration 0006: `result.job_id`, `provenance.job_id` `CASCADE` → `RESTRICT` (owner option B) | `migrations/versions/0006_*`, design note `migration-0006-design-note.md`, tests `test_migration_0006.py` |
| Compose: PostGIS healthcheck over TCP; credentials for PostGIS and services from the same `.env` (`env_file`), never interpolated | `infrastructure/docker/docker-compose.yml`, `infrastructure/README.md`, `tests/unit/test_image_packaging.py` |
| `GET /api/v1/connectors` (fixture-only capability; no hosts, no input) | `app/api/connectors.py` |
| `GET /api/v1/aois/{id}/assets` (AOI-scoped, `created_at,id` order, limit 1–100/offset, optional `job_id`) | `app/api/aois.py` |
| Named provenance helper `build_provenance_record` (behaviour unchanged) | `geo_connectors/provenance.py`, `test_provenance.py` |
| Confirmed API contract (owner, 2026-10-06): `409 has_results`; `501 connector_live_not_available`; top-level `aoi_id`; project derived from the AOI only; refusal order 422 → mode → 404 → 429/503 | `docs/connectors.md` §3 |
| **10-collection cap: a temporary fixtures-only operational bound**, not a provider/API capability; validated and tested; to be revisited before any live catalogue slice | `app/catalog_jobs.py`, `docs/connectors.md` |

## 2. Acceptance matrix T1–T11
Labels: **passed** = executed and green on real PostgreSQL/HTTP/filesystem/process (or image); **simulated** = injected fault or seam, not concurrency evidence; **policy-only** = static/source check, not a runtime guarantee; **deferred**; **n/a**.

| Case | Classification | Basis |
|---|---|---|
| T1 migrations | **passed** | 0004, 0005, 0006: up/down/up, seeded rows, abort rules, introspection (0006: `confdeltype='r'`, immediate, validated) |
| T2 database integrity | **passed** | direct SQL, job- and asset-level cases |
| T3 jobs API | **passed**; busy-queue 503 mapping for `catalog_search` is **simulated** (stub); the real budget exhaustion is **passed** (`test_jobs_busy_api.py`) | modes, targeting, no client project, limits, queue limits |
| T4 fixture run end to end | **passed** (API → queue → runner child → handler; real worker-death-after-publication retry; zero results → `insufficient_data` with no result/envelope/asset); also **passed** inside the built worker image (`scripts/image_smoke.sh`) | |
| T5 no external network | (a) connector-window guard **passed**; (b) whole-path socket audit **passed** as an audit of that code path (handler and runner child), **not an egress firewall**; (c) import rules **policy-only** | |
| T6 deletion, tombstones, drain, reconcile | **passed**; storage-fault and post-commit-failure cases **simulated**; report-only `make reconcile-assets` **passed** (run as the real command) | |
| T7 concurrency | T-D1–T-D10, T-D12, T-D13 **passed** (real sessions); T-D11, T-D15 **simulated**; T-D14 **policy-only** | unchanged since CP3 |
| T8 architecture | **policy-only** | import/dependency rules; image packaging rules |
| T9 guards | **policy-only** (forbidden-term scan incl. `.sh`, allow-listed shapes, `CONNECTOR_MODE` default); the real job output is **passed** in the flow test | |
| T10 full local CI and Actions | **passed** (`make ci-full`; Actions result reported per exact SHA) | |
| T11 licence register, no new third-party package | **passed** (`make licences`; no third-party package added. Relative to the pre-3a baseline `6b8d15e`, `uv.lock` and `pyproject.toml` did change, to add the workspace member `geo-connectors`, which depends only on `geo-common`; it was unchanged by CP4 and the closure checkpoint) | |
| Live provider behaviour, live verification (D8 R1–R8), F-1 closure | **deferred** — not part of fixtures-only 3a; required before any live slice | |
| UI for jobs/assets | **n/a** (not authorised) | |

## 3. Remaining limitations and live-slice requirements
* Nothing live exists; no behaviour against a real catalogue has been verified. A live slice needs: F-1 closed; D8 readiness R1–R8; the owner's approval of exact hosts/ports and of application and network controls; HTTP-client selection per ADR-0014 §9/§10; a new start instruction.
* The 10-collection cap, the 409/501 codes and `max_items` rules are fixtures-only choices to revisit before a live catalogue slice.
* Foreign-key actions do not stop `TRUNCATE … CASCADE`, `DELETE FROM result`, DROP, a superuser or restoring an older backup; the application guard is required in addition.
* The socket audit is evidence for tested code paths only.
* Asset size cap provisionally reuses `MAX_UPLOAD_MB`; `user_vector`/`dem_clip` kinds exist in the CHECK with no code path.
