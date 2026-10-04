# Phase 1 Plan — Repo/App Foundation

Status: **APPROVED (2026-10-04) — in implementation.** T8 approved and recorded as ADR-0011. Implementation notes and deviations are listed in `docs/phase-reports/phase-1.md`.
Governing decisions: ADR-0001…0010 (`docs/adr/`). Acceptance: `docs/acceptance-criteria.md` → Phase 1.

## 1. Goal and boundaries

**Goal:** a running, tested, CI-checked skeleton on which later phases can be built: Compose stack, API, PostgreSQL/PostGIS schema, PostgreSQL-backed job queue with a worker, local storage, shared schemas with the mandatory result envelope, a minimal frontend status page, and scientific-guard tests.

**Explicitly NOT in Phase 1:** AOI endpoints or UI, maps, connectors, Earth Engine, any scientific engine or fake result, authentication, Redis, MinIO, Cesium, report generation. The only job type is `noop`. No endpoint returns a scientific result.

## 2. Technical choices needing owner approval

These are proposals (confidence: *likely* suitable; versions must be verified when implementing). Anything unapproved defaults to "ask".

| # | Choice | Proposal | Why |
|---|---|---|---|
| T1 | Python version / env tool | Python 3.12, `uv` with committed lockfile | Fast, reproducible; replaces pip-tools/poetry/conda for Phase 1. Conda may be needed later for GDAL-heavy/geophysics images (revisit in Phase 2/8). |
| T2 | Python quality tools | `ruff` (lint+format), `mypy` (strict on shared lib + backend), `pytest` | Standard, fast |
| T3 | Backend libs | FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x (Core-first for queue SQL), ~~psycopg 3~~ **pg8000** (see phase report deviation 1), Alembic | Mainstream, typed |
| T4 | Node tooling | Node LTS, **npm** (lockfile committed), ESLint, Prettier, `tsc --noEmit`, Vitest | Fewest moving parts |
| T5 | Schema codegen | JSON Schema → Pydantic via `datamodel-code-generator`; JSON Schema → TS via `json-schema-to-typescript` | Keeps `packages/schemas` the source of truth |
| T6 | DB image | `postgis/postgis` (pinned tag, PostgreSQL 16 line) | Official PostGIS image |
| T7 | Secret scan | `gitleaks` in CI + pre-commit | Free/open |
| T8 | **New shared Python package `packages/pycommon/`** (`geo_common`): config base, `StorageBackend`, `JobQueue`, generated envelope models | Workers must not import backend code (architecture rule), yet both need queue/storage/envelope code. This is a **structural change** → file as **ADR-0011** on approval. |
| T9 | Worker runner location | `workers/runner/` (generic loop + `noop` handler); future engines are sibling dirs | Matches existing layout |

## 3. Ordered task list

Each task: **Do** · **Files** · **Done when** (verifiable). Tasks are small enough for one commit each (`phase-1: …`). Dependencies in brackets.

### P1-01 Repo tooling baseline
- **Do:** `.editorconfig`, `.pre-commit-config.yaml` (ruff, prettier, gitleaks, end-of-file/trailing-space), top-level `Makefile` with targets `lint test up down migrate`, dev section in README.
- **Done when:** `pre-commit run --all-files` passes on a clean checkout; `make lint` runs (even if sub-projects are empty stubs).

### P1-02 Python workspace [P1-01]
- **Do:** `pyproject.toml` + lockfile for `packages/pycommon`, `apps/backend`, `workers/runner` (uv workspace); ruff/mypy/pytest config; empty-but-importable packages.
- **Files:** `packages/pycommon/`, `apps/backend/pyproject.toml`, `workers/runner/pyproject.toml`.
- **Done when:** `uv sync` succeeds; `uv run pytest` collects (zero or smoke) tests; `mypy` passes; backend and runner can import `geo_common`; **grep test proves runner does not import `app.*` (backend)**.

### P1-03 Typed configuration [P1-02]
- **Do:** `geo_common.config.Settings` (pydantic-settings) with every variable in `.env.example`, including ADR-0008 limits, queue settings and `ENABLE_EARTH_ENGINE` (default false). Fail fast on invalid values (negatives, zero limits, `MIN_AOI_AREA_KM2 >= MAX_AOI_AREA_KM2`); log a warning if the circle area from `MAX_RADIUS_KM` (π·r²) exceeds `MAX_AOI_AREA_KM2`.
- **Done when:** unit tests cover defaults, overrides, invalid values; a test asserts the set of keys in `.env.example` equals the `Settings` fields (no drift); no variable for Redis/S3/auth exists.

### P1-04 Database & migrations [P1-02, P1-03]
- **Do:** SQLAlchemy engine factory; Alembic env; migration `0001` enabling `postgis` and creating:
  - `aoi(id uuid pk, name text, geom geometry(Polygon,4326), source text, created_at)` — table only, no API in Phase 1
  - `job(id uuid pk, type text, status text check in (queued,running,succeeded,failed,cancelled,insufficient_data), priority int, payload jsonb, attempts int, max_attempts int, locked_by text, lease_expires_at timestamptz, cancel_requested bool, error text, created_at, started_at, finished_at)` + partial index on `(priority, created_at) WHERE status='queued'`
  - `result(id uuid pk, job_id fk, kind text, envelope jsonb, created_at)`
  - `provenance(id uuid pk, job_id fk, record jsonb, created_at)`
- **Done when:** `alembic upgrade head` then `alembic downgrade base` then `upgrade head` all succeed against a fresh PostGIS container; a test confirms the `postgis` extension and a `Polygon,4326` geometry round-trip; constraint rejects invalid `status`.

### P1-05 StorageBackend + LocalStorage [P1-03]
- **Do:** interface (`put`, `get`, `exists`, `delete`, `open_path`) and `LocalStorage` rooted at `STORAGE_LOCAL_PATH`; logical keys only.
- **Done when:** tests prove round-trip, overwrite semantics, and **rejection** of `../x`, absolute paths, symlink escape, empty keys, NUL bytes; no MinIO/S3 code or dependency present.

### P1-06 JobQueue + PostgresJobQueue [P1-04]
- **Do:** interface (`enqueue`, `claim`, `heartbeat`, `complete`, `fail`, `cancel`, `requeue_expired`) and SQL implementation per ADR-0007 (`FOR UPDATE SKIP LOCKED`, lease, attempts, `MAX_QUEUED_JOBS` check inside the enqueue transaction).
- **Done when (integration tests against real PostGIS):** N concurrent claimers never claim the same job; expired lease returns job to `queued` and increments attempts; exceeding `max_attempts` → `failed` with reason; cancel of a queued job is immediate, of a running job sets `cancel_requested`; enqueue beyond `MAX_QUEUED_JOBS` is rejected; priority ordering respected.

### P1-07 Worker runner [P1-06, P1-05]
- **Do:** loop: claim → run handler in a **child process** → heartbeat thread/timer → enforce `JOB_TIMEOUT_SECONDS` by killing the child → record terminal state. Handler registry with a single `noop` handler (sleeps optional N s, returns success; optionally returns `insufficient_data` for test).
- **Done when:** tests show success path, handler exception → `failed` with message, timeout kill → `failed` (reason `timeout`), cancel-while-running honoured, worker crash (SIGKILL) leaves job recoverable by lease expiry, graceful SIGTERM stops claiming and finishes/aborts cleanly. Worker logs contain job id; no AOI contents at INFO.

### P1-08 FastAPI skeleton [P1-03, P1-04]
- **Do:** app factory; `GET /api/v1/health` (liveness) and `GET /api/v1/health/ready` (DB reachable); structured JSON logging with request id; uniform error body; CORS allow-list from `CORS_ALLOWED_ORIGINS`; request-body size cap; OpenAPI served; no admin/debug routes.
- **Done when:** tests for health, readiness failure when DB down, CORS allowed/denied origin, oversize body rejected; OpenAPI snapshot test committed.

### P1-09 Jobs API (noop only) [P1-06, P1-08]
- **Do:** `POST /api/v1/jobs` (type allow-list `["noop"]`; unknown type → 422), `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel`. Limits from `Settings`. No result-producing endpoints.
- **Done when:** end-to-end test (API → `job` row → worker → status `succeeded` visible via GET); queue-full returns a clear 429/409-style error naming `MAX_QUEUED_JOBS`; cancel works; no endpoint accepts or returns an AOI.

### P1-10 Shared schemas & result envelope [P1-02]
- **Do:** in `packages/schemas/`: JSON Schemas for `Job`, `ResultEnvelope`, `Provenance`, `Evidence`, `Source`, `Disclaimer`. `ResultEnvelope` requires `kind`, `confidence{level,basis}`, `uncertainty{method|not_quantified+reason}`, `explanation`, `sources[]`, `provenance`, `disclaimer_id`, `validation_status` (**enum: `unvalidated` only**), `calibration_status` (default `uncalibrated`), `engine_status` (default `experimental`); `kind` enum excludes any `confirmed_*`; `depth` allowed only with `depth_basis ∈ {field_geophysics, direct_verification}`; optional `deposit_model` (`orogenic`) + `applicability`. Codegen scripts produce Pydantic (in `geo_common`) and TS types.
- **Done when:** `make schemas` regenerates; CI fails if generated files differ from committed ones; valid/invalid fixture tests cover every required field missing, bad enum values, `depth` without basis, `validation_status="validated"` (rejected).

### P1-11 Envelope-enforcing serialiser [P1-10]
- **Do:** `geo_common.envelope.serialise_result()` used by any future result route; raises (never defaults) when a mandatory field is missing. Wire a FastAPI response helper that returns 500 with an explicit "incomplete result refused" error.
- **Done when:** unit tests prove refusal for each missing field and that nothing is auto-filled with a flattering default. (No result route is exposed in Phase 1.)

### P1-12 Third-party licence register [P1-02, P1-04]
- **Do:** create `docs/third-party-licences.md` listing every Phase 1 runtime dependency (backend, runner, frontend, base images): name, version, licence (verified from the package metadata/upstream), usage mode, date verified. Add a CI check that fails when a lockfile dependency is absent from the register (simple script).
- **Done when:** check passes; any copyleft entry is flagged for owner approval (CLAUDE.md §6).

### P1-13 Docker Compose stack [P1-02, P1-04, P1-07, P1-08]
- **Do:** `infrastructure/docker/` Dockerfiles (backend, worker) and `docker-compose.yml` with `postgis`, `backend`, `worker`, `frontend`; ports published as `${BIND_HOST}:port` (default `127.0.0.1`); named volumes for PostgreSQL data and `STORAGE_LOCAL_PATH` shared by backend/worker; healthchecks; migration step on backend start (or one-shot `migrate` service). No Redis, no MinIO.
- **Done when:** from a clean clone with `cp .env.example .env`, `docker compose up --build` reaches healthy; `curl 127.0.0.1:8000/api/v1/health/ready` OK; a test (or scripted check) confirms published ports are bound to loopback only; `docker compose config` shows no `redis`/`minio` services.

### P1-14 Frontend skeleton [P1-10, P1-13]
- **Do:** Next.js (TypeScript, App Router) in `apps/frontend`; ESLint/Prettier/`tsc`; status page showing backend readiness and a button to submit a `noop` job and display its status (polling); persistent footer with the scientific disclaimer D-1 text; generated TS types consumed. No map libraries yet.
- **Done when:** `npm run lint && npm run typecheck && npm test && npm run build` pass; Compose frontend loads; manual check recorded: submit noop → see `succeeded`.

### P1-15 Scientific-guard tests [P1-10, P1-14]
- **Do:** `tests/scientific/`:
  1. **Forbidden-term scan** (ADR-0009) over source, schemas, fixtures and UI strings; config lists forbidden stems and an explicit allow-list of doc files (docs may discuss them).
  2. Envelope completeness per fixture.
  3. `validation_status` can only be `unvalidated`.
  4. Depth gating.
  5. Repo-policy checks: no `redis`, `minio`, `boto3`, auth libraries (`passlib`, `jwt`, OAuth) in lockfiles (ADR-0005/0006/0007); `ENABLE_EARTH_ENGINE` default is false; `.env.example` contains no non-placeholder secret patterns.
- **Done when:** all pass in CI; a deliberate temporary violation (documented in the PR/commit message, then reverted) is shown to fail the scan.

### P1-16 CI workflow [P1-01…P1-15]
- **Do:** `.github/workflows/ci.yml`: jobs for Python (ruff, mypy, pytest unit), integration (PostGIS service container), schemas-drift, frontend (lint/typecheck/test/build), gitleaks, scientific guard, licence register check, Docker build smoke (no push). No live network calls to data providers; no Earth Engine. Minimise CI minutes (cache, path filters) — private repo (ADR-0001).
- **Done when:** workflow green on the Phase 1 branch; a seeded failing test turns it red (verified once, reverted).

### P1-17 Security hygiene [P1-08, P1-13]
- **Do:** dependency vulnerability audit commands (`pip-audit`/`npm audit`) in CI as non-blocking report initially; document the no-auth stance in the README top and API docs description; logging review (no secrets, no AOI at INFO); container runs as non-root; `.dockerignore`.
- **Done when:** checks present and documented; findings (if any) triaged in the PR.

### P1-18 Phase 1 acceptance run & doc sync [all]
- **Do:** clean-clone dry run following only README instructions; walk through every Phase 1 criterion in `docs/acceptance-criteria.md`, record evidence (command output) in `docs/phase-reports/phase-1.md`; tick `TASKS.md` boxes only for verified items; update `docs/architecture.md` if reality differs; file ADR-0011 (if T8 approved).
- **Done when:** all Phase 1 criteria checked with evidence; owner confirms; only then Phase 2 may start.

## 4. Dependency graph (summary)

```
P1-01 → P1-02 → P1-03 → P1-04 → P1-06 → P1-07 ─┐
                  │        │        └→ P1-09     ├→ P1-13 → P1-14 → P1-15 → P1-16 → P1-17 → P1-18
                  │        └→ P1-08 ─┘            │
                  ├→ P1-05 ──────────────────────┘
                  └→ P1-10 → P1-11 ;  P1-12
```
Suggested commit/PR grouping: (A) P1-01–03; (B) P1-04–07; (C) P1-08–09; (D) P1-10–12; (E) P1-13–14; (F) P1-15–18. Owner reviews at the end of each group.

## 5. Phase 1 risks and mitigations

| Risk | Mitigation |
|---|---|
| Hand-written queue is subtly wrong (P-5) | Integration tests in P1-06/07 are acceptance-critical; do not skip |
| Scope creep into AOI/map work | CLAUDE.md §2; `aoi` has a table only, no API/UI |
| Forbidden-term scan too noisy or too weak | Explicit stem list + allow-list; one deliberate-violation check (P1-15) |
| Toolchain version drift | Lockfiles; versions recorded in `third-party-licences.md` |
| CI minutes on private repo | Path filters, caching, single OS |
| Docker/DB unavailable in this cloud session | State clearly in reports which checks were run vs not run |

## 6. Approval requested

1. Approve (or amend) T1–T9, notably **T8 (`packages/pycommon`)**.
2. Approve task list and grouping.
3. Confirm ADR-0010 field-validation definitions (not blocking Phase 1; blocking Phase 5/9 design).
