# Phase 1 Closeout

Status: **accepted by the owner with follow-up checks** (2026-10-04). This file records what was accepted, what remains open, and what was deferred.
**No analysis, scoring, AOI science, remote-sensing or Earth Engine logic exists.** Phase 1 delivered infrastructure only; Phase 2 adds AOI geometry input (still no analysis).

## 1. Owner decisions at acceptance
> **Historical summary (corrected 2026-10-05).** This section is Claude's summary of the owner's message of 2026-10-04, not a verbatim transcription. Item 3 below originally dropped the owner's words "for now" and added "unmodified"; it is corrected to the owner's exact decision and its narrower scope. The verbatim text of decision 3 is: *"The listed weak-copyleft/transitive packages are acknowledged for now and do not block Phase 2. Strong copyleft remains blocked."* Scope (see `docs/licence-acknowledgements.toml`, OA-0001): a provisional acknowledgement, by name, of the packages named in the question that preceded it (`certifi`, `pathspec`, `axe-core`, `lightningcss`, `@img/sharp-*` — 18 register entries); effect limited to "did not block Phase 2"; versions are observed evidence, not approved scope; redistribution, licence compliance and licence conditions were not addressed; the 11 `lightningcss-<platform>` packages remain pending; it is not extended to Phase 3 automatically.
1. **pg8000 stays** as the PostgreSQL driver; switch back to psycopg only for a strong technical reason.
2. The optional **`proxy_ca` build secret** is acceptable while it stays empty by default and documented (`infrastructure/README.md`, root README). Its empty default file is `infrastructure/docker/no-ca.crt`.
3. **Weak-copyleft/transitive packages** named in the owner's question (see the note above) are acknowledged **for now** and do not block Phase 2. Strong copyleft remains blocked (enforced by `scripts/licences.py`).

## 2. Follow-up checks requested, and their status
| Follow-up | Status |
|---|---|
| Let the first GitHub Actions run finish and fix workflow issues | **Done.** Run #1 and #2 failed on two real defects: (a) `*.pem` was git-ignored, so the empty default CA file was never committed and `docker compose build` failed; (b) generated Pydantic code was formatted differently by pre-commit than by the generator, so the schema-drift check failed. Both fixed in `bbab3c8`; run #3 concluded `success`. The local `make ci` had not caught either, which is the argument for running CI early. |
| Phase 1 closeout summary | This file. |
| Document the job lifecycle | `docs/job-lifecycle.md` (states, transitions, guarantees, timings). |
| Document queue-capacity assumptions as provisional | `docs/job-lifecycle.md` §5 and ADR-0008: 1 worker, `MAX_QUEUED_JOBS=10`, 1800 s timeout are **unmeasured guesses**. |
| Keep explicit that no analysis exists | Stated above, in the README banner, in the API description and in `docs/phase-2-plan.md`; enforced by `tests/unit/test_architecture.py` (no engine code, no analysis imports in the backend) and `tests/scientific`. |

## 3. Accepted items
Compose stack (postgis, migrate, backend, worker, frontend; loopback ports; no Redis/MinIO), FastAPI skeleton, PostgreSQL-backed `JobQueue` with worker, local `StorageBackend`, shared contracts and result-envelope guard (`validation_status` only `unvalidated`), `geo_common` shared package (ADR-0011), CI workflow, licence register, scientific-guard tests. Evidence: `docs/phase-reports/phase-1.md`.

## 4. Open risks (carried forward)
| Risk | Note |
|---|---|
| Queue durability semantics | Execution is **at-least-once**; engines must be idempotent (`docs/job-lifecycle.md` §3). |
| Unbounded `job` row growth | No retention/purge policy exists yet. |
| Capacity limits unmeasured | ADR-0008 values are guesses until profiled (reference hardware still undefined). |
| `WORKER_CONCURRENCY>1` unsupported | Accepted by config, ignored with a warning. |
| No authentication (ADR-0005) | Local/loopback use only; any shared deployment is blocked until a new ADR. |
| Earth Engine eligibility | Nothing built; the account owner must still validate commercial eligibility in writing (ADR-0004 amendment). |
| Dependency audits | The CI `audit` job is report-only; its findings have **not been reviewed or triaged**. |
| GitHub Actions Node 20 deprecation notice | `checkout@v4`, `setup-node@v4`, `setup-uv@v5` are forced onto Node 24 by GitHub; bump the action versions when convenient. |
| Phase 5 gate | Scientific design must not start until the owner defines the target country/region and pilot area (ADR-0003 amendment). |

## 5. Deferred items
Job retention/purge; worker concurrency > 1; triage of `pip-audit`/`npm audit`; metrics/observability beyond JSON logs; load/throughput profiling; moving the CI action versions off Node 20; switching to a Postgres queue library or RQ if the hand-written queue ever becomes a maintenance burden (ADR-0007).
