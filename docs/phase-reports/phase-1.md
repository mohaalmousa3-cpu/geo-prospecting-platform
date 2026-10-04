# Phase 1 Report — Repo/App Foundation

Status: **accepted by the owner with follow-up checks (2026-10-04)** — see `docs/phase-reports/phase-1-closeout.md`. CI note: this report says GitHub Actions had not run; runs #1–#2 later failed on two defects and run #3 passed (closeout §2).
Date: 2026-10-04 · Branch: `claude/geo-prospecting-foundation-hmcma4`

## 1. Scope delivered
Infrastructure, API skeleton, PostgreSQL-backed job queue and worker, local storage abstraction, shared contracts and result envelope, health checks, frontend status page, CI definition, licence register, scientific-guard tests. **No analysis engine, no scientific scoring, no AOI endpoints, no connectors, no map code, no Earth Engine code exist.** The only job type is `noop`; no endpoint returns a scientific result.

## 2. Task status (P1-xx from `docs/phase-1-plan.md`)
| Task | Status | Evidence |
|---|---|---|
| P1-01 tooling baseline | Done | `.editorconfig`, `.pre-commit-config.yaml`, `Makefile`; `pre-commit run --all-files` passed (incl. gitleaks) |
| P1-02 Python workspace | Done | uv workspace, lockfile, ruff/mypy/pytest; `tests/unit/test_architecture.py` enforces import direction |
| P1-03 typed config | Done | `geo_common.config.Settings`; test asserts `.env.example` keys == Settings fields |
| P1-04 DB & migrations | Done | Alembic `0001`; up→down→up test; PostGIS geometry round-trip; CHECK constraints tested |
| P1-05 StorageBackend | Done | traversal / absolute / symlink / NUL / empty keys rejected (tests) |
| P1-06 JobQueue + Postgres | Done | see §3 |
| P1-07 Worker runner | Done | see §3 |
| P1-08 FastAPI skeleton | Done | health, readiness (503 when DB down), CORS allow-list, body cap, request id, OpenAPI snapshot |
| P1-09 Jobs API (noop) | Done | API→DB→worker→API e2e test; queue-full 429 naming `MAX_QUEUED_JOBS` |
| P1-10 Schemas & envelope | Done | `packages/schemas/geo-contracts.schema.json`; Pydantic + TS generated; drift check in `make schemas-check` |
| P1-11 Envelope serialiser | Done | `geo_common.envelope.serialise_result` refuses every missing field; never defaults |
| P1-12 Licence register | Done | `docs/third-party-licences.md` generated from metadata/lockfiles; check script |
| P1-13 Docker Compose | Done | built and run, see §4 |
| P1-14 Frontend skeleton | Done | lint, typecheck, prettier, 5 vitest tests, production build; served in Compose (HTTP 200) |
| P1-15 Scientific guards | Done | forbidden-term scan (+ deliberate-violation check), policy checks |
| P1-16 CI workflow | Written, **not executed on GitHub** | `.github/workflows/ci.yml`; same commands run locally via `make ci` (exit 0) |
| P1-17 Security hygiene | Partly | non-root containers, `.dockerignore`, loopback binding verified; `pip-audit`/`npm audit` are in CI as report-only and **have not been run or triaged** |
| P1-18 Acceptance run | This report | owner confirmation pending |

## 3. Mandatory queue tests (ADR-0007) — all passing against real PostGIS 3.4 / PostgreSQL 16
- **Concurrency:** 12 threads claim 50 jobs → each exactly once; enqueue under 16 threads with `MAX_QUEUED_JOBS=5` → exactly 5 accepted; concurrent recovery sweeps recover each expired job exactly once.
- **Lease renewal:** heartbeat extends the lease and rejects non-owners; a job outliving its original lease is not stolen while heartbeats continue (also with the real runner).
- **Retry:** retryable failure requeues until `max_attempts`, then fails; handler exceptions are terminal; hard process crash is retried then failed.
- **Recovery:** expired lease → requeued; stale worker can no longer complete/fail/heartbeat; exhausted attempts → `failed` with reason; cancel-requested jobs are not resurrected after a crash; lease loss makes the runner abandon the job without overwriting state.
- **Timeout / cancel / shutdown:** child process killed at timeout; cancel while running honoured; SIGTERM-style stop returns the job to the queue.
- **Mutation check:** removing `FOR UPDATE SKIP LOCKED` made the double-claim test fail (the test really tests the property).

## 4. Verification actually performed (this session)
| Check | Result |
|---|---|
| `make ci` (ruff, ruff format, mypy, unit, integration, guards, licence check, frontend lint/type/format/test/build, schema drift) | exit 0 |
| Python tests | 136 passed (83 unit + 53 integration, incl. 24 scientific/guard tests counted inside) |
| Frontend tests | 5 passed |
| Docker: `docker compose up --build` from a **fresh clone** of the pushed branch, `cp .env.example .env` | all services healthy |
| Ports | backend/frontend published on `127.0.0.1` only; PostgreSQL not published |
| Services present | postgis, migrate, backend, worker, frontend — **no Redis, no MinIO** |
| `noop` job via real containers | queued → succeeded (attempt 1) |
| Queue full | first 10 accepted, next 3 → HTTP 429 `queue_full`, message names `MAX_QUEUED_JOBS=10` |
| `SIGKILL` worker mid-job, restart | orphaned job reclaimed after lease expiry (attempt 2) |
| Deliberate forbidden-term violation | scan failed, then reverted |

## 5. Not verified / limitations (honest list)
- **GitHub Actions has not run.** `ci.yml` is syntax-checked (YAML) and mirrors `make ci`; action versions (`checkout@v4`, `setup-uv@v5`, `setup-node@v4`) and `zricethezav/gitleaks:latest` were not exercised. Treat first CI run as a test of the workflow itself.
- PostgreSQL for local tests was a system install (PG 16 + PostGIS 3.4 packages), CI/Compose use the `postgis/postgis:16-3.4` image; the Compose run used that image.
- Dependency vulnerability audits were not run or triaged.
- Throughput/latency and resource use were not measured; ADR-0008 limits remain unmeasured guesses (provisional operational safeguards, not scientific thresholds).
- Frontend manual browser check was not done; the page was verified by unit tests, build, and an HTTP 200 from the container.
- `WORKER_CONCURRENCY > 1` is accepted by config but unsupported (the worker runs one job at a time and logs a warning).
- The licence register's "NOT INSTALLED" entries (platform-specific wheels such as `tzdata`/`colorama`) were not verified.

## 6. Deviations from `docs/phase-1-plan.md`
1. **Driver: `pg8000` (BSD-3-Clause) instead of `psycopg` 3.** psycopg is LGPL-3.0; adding a copyleft runtime dependency needs owner approval (CLAUDE.md §6), so I avoided the question. Reversible if you prefer psycopg.
2. **Docker build secret `proxy_ca`** (optional) added to Dockerfiles/Compose so images build behind TLS-intercepting proxies. Default is an empty file; no behaviour change otherwise.
3. **Pre-commit ruff runs as a local hook** (`uv run ruff`) so versions cannot drift from the lockfile.
4. `make up` expects `./.env` (copied from `.env.example`); `POSTGRES_PASSWORD` has no usable default in Compose (`:?` guard) — you must set one.
5. Python lock/venv: Python 3.12 (`.python-version`).
6. Priority ordering is "higher number first" (ADR text said only "order by priority").
7. `JobQueue.complete()` also accepts `CANCELLED` so a cancelled running job ends in `cancelled` rather than `failed`.

## 7. Items needing owner decision
1. **Weak-copyleft packages** (LGPL/MPL, unmodified, no vendored source) are listed under *Pending owner acknowledgement* in `docs/third-party-licences.md`: `certifi` (MPL-2.0), `pathspec` (MPL-2.0, dev), `axe-core` and `lightningcss` (MPL-2.0, frontend dev tooling), and `@img/sharp-*` (LGPL-3.0, optional native packages pulled by Next.js). Nothing is marked approved. Strong copyleft (GPL/AGPL/EUPL) is blocked by the check and none is present.
2. Confirm pg8000 vs psycopg (deviation 1).
3. Accept Phase 1 → permission to start Phase 2 (AOI input and map basics). Phase 5 remains gated on target region + pilot area (ADR-0003 amendment); **Phase 2 does not need them.**
4. Earth Engine: nothing was built; commercial eligibility must still be validated by the account owner before any operational use (ADR-0004 amendment).
