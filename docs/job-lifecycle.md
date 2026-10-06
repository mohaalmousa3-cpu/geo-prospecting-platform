# Job Lifecycle and Queue Capacity

Applies to the PostgreSQL-backed queue (ADR-0007). **No analysis, scoring, AOI science or Earth Engine logic exists.** The only job type today is `noop`; this document describes the mechanism that later engines will run on.

## 1. States

```
                     cancel (immediate)
        ┌────────────────────────────────────────────┐
        │                                            ▼
  enqueue ──► queued ──claim──► running ──► succeeded
                ▲                  │  ├────► insufficient_data   (normal, explained outcome)
                │                  │  ├────► failed
                │  lease expired / │  └────► cancelled           (cancel honoured while running)
                └─ crash / shutdown┘
                 (attempts < max_attempts)
```

| Status | Terminal | Meaning |
|---|---|---|
| `queued` | no | Waiting for a worker. Counts against `MAX_QUEUED_JOBS`. |
| `running` | no | Claimed by exactly one worker holding an unexpired lease. |
| `succeeded` | yes | Handler finished normally. |
| `insufficient_data` | yes | Handler reports it cannot produce a result from the available data. A normal outcome, not an error. |
| `failed` | yes | Handler error, timeout, repeated crashes, or lease/attempts exhausted. `error` holds the reason (≤ 2000 chars). |
| `cancelled` | yes | Cancelled while queued, or while running and honoured by the worker. |

Before enqueue (synchronously in the API): request received → payload validated → limits checked (ADR-0008) → row inserted. A rejected request never creates a job.

## 2. Transitions

| From → To | Trigger | Notes |
|---|---|---|
| (new) → `queued` | `POST /api/v1/jobs` | Rejected with HTTP 429 `queue_full` when `queued` count ≥ `MAX_QUEUED_JOBS` (checked under an advisory lock, so concurrent requests cannot overshoot). |
| `queued` → `running` | worker `claim` | `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`; order: higher `priority` first, then oldest. Increments `attempts`, sets `locked_by`, `lease_expires_at`. |
| `running` → `running` | `heartbeat` | Worker extends the lease every `lease/3` seconds. Fails (`owned=false`) if the job no longer belongs to this worker; the worker then kills its child and **writes nothing**. |
| `running` → `succeeded` / `insufficient_data` | `complete` | Only the current lock owner can complete. |
| `running` → `failed` | `fail` | Handler exception, timeout (`JOB_TIMEOUT_SECONDS`), unknown job type. Not retried. |
| `running` → `queued` | retryable `fail`, or `requeue_expired` | Handler process died (crash / OOM kill), worker shut down mid-job, or the lease expired. Only while `attempts < max_attempts`; otherwise → `failed` (`lease expired; max attempts exhausted`). |
| `queued` → `cancelled` | `POST …/cancel` | Immediate. |
| `running` → `cancelled` | `POST …/cancel` then worker heartbeat | `cancel_requested` is set; the worker sees it on its next heartbeat (≤ `lease/3`), kills the handler, records `cancelled`. If the worker crashed instead, recovery turns it into `cancelled` rather than re-queueing it. |
| terminal → anything | — | Never. `cancel` on a terminal job is a no-op. |

## 3. Guarantees and non-guarantees
- **Exactly one active owner** at a time (tested with 12 concurrent claimers over 50 jobs).
- **At-least-once execution, not exactly-once.** After a crash or lease expiry the same job may run again (attempt 2). **Handlers must be idempotent** and must write results atomically/keyed by job id. A stale worker can no longer complete, fail or heartbeat a job it lost (tested), but its side effects, if any, are not rolled back.
- Retries: `max_attempts` counts *all* attempts including the first (default `JOB_MAX_ATTEMPTS=2`). Handler exceptions and timeouts are never retried.
- Ordering is best-effort priority-then-age; no fairness across job types.
- Cancellation of a running job is cooperative-by-kill: the handler process is killed, not asked to stop. Handlers must tolerate being killed.
- No result or job retention policy exists yet: `job` rows accumulate (see closeout, deferred items).

## 4. Time parameters (all env-configurable)
| Setting | Default | Role |
|---|---|---|
| `JOB_LEASE_SECONDS` | 60 | Lease granted at claim and on each heartbeat |
| heartbeat interval | lease / 3 (20 s) | Not separately configurable |
| `WORKER_POLL_INTERVAL_SECONDS` | 2 | Idle polling; also the sweep for expired leases |
| `JOB_TIMEOUT_SECONDS` | 1800 | Hard kill of the handler process |
| `JOB_MAX_ATTEMPTS` | 2 | Attempts incl. first |

Worst-case delays: crash detection ≈ `lease` + poll (≈ 62 s default, observed in the Docker test); cancel of a running job ≈ `lease/3` (≈ 20 s default).

## 5. Capacity assumptions — **provisional, unmeasured** (ADR-0007, ADR-0008)
These are conservative operational safeguards for a single local machine. They are **not** performance results and **not** scientific thresholds.

| Assumption | Value | Basis |
|---|---|---|
| Workers / concurrency | 1 worker, 1 job at a time | `WORKER_CONCURRENCY>1` is accepted by config but unsupported in Phase 1 |
| Queue depth | `MAX_QUEUED_JOBS=10` (running jobs are not counted, so ≤ 11 unfinished jobs) | guess |
| Timeout | 1800 s per job | guess |
| Theoretical drain time of a full queue | up to 11 × 1800 s ≈ 5.5 h | arithmetic on the guesses above |
| Dispatch latency | ≤ poll interval (2 s) | by design; not benchmarked |
| Throughput / DB load | not measured | — |

To be re-evaluated after Phase 3–4 profiling on the reference hardware (still undefined). Changing any of them requires updating ADR-0008 and this section; raising them must not silently change scientific behaviour.

## 5a. AOI-bound jobs and the cancelled-job asset rule (Phase 3a; ADR-0014)
- **AOI binding (migration 0004, implemented):** a job has `aoi_id` and `project_id` both set or both NULL. Only `noop` may be AOI-free; every other type needs an AOI. `JobQueue.enqueue(job_type, payload, *, aoi_id=...)` requires `aoi_id` for non-`noop` types (`ValueError` before any SQL), derives the project from the AOI row in one `INSERT … SELECT`, and raises `JobTargetNotFoundError` if the AOI does not exist or vanishes before commit. `enqueue` runs in the whole-transaction retry wrapper (`geo_common.transactions`) and raises `QueueBusyError` when its attempt budget is exhausted.
- **Deliberate lifecycle rule for staged assets (owner decision 2026-10-05; implemented in Phase 3a CP3: `publish_asset` verifies under locks that the job is running, owned by the publishing worker, in the expected AOI/project and not `cancel_requested`; the runner completes the job only after the handler returns):** assets that were successfully published *before* a job is marked `cancelled` **may remain linked to that cancelled job**. Conditions: (1) the publication transaction first verifies that the job is still `running`, owned by the publishing worker and not `cancel_requested`; (2) completion happens only *after* successful publication; (3) a cancellation observed before publication prevents publication and triggers cleanup of the temporary file; (4) deleting the AOI or project still removes those assets through the accepted cascade path (ADR-0014 §7.5/§8). This is a rule, not an accident: cancelled jobs can therefore own assets.
- **Terminal statuses** for deletion decisions: `succeeded`, `failed`, `cancelled`, `insufficient_data`. The transition code never moves a job out of a terminal status (policy check T-D14; not a database-enforced guarantee).

## 6. API mapping (Phase 1)
`POST /api/v1/jobs` → 201 `Job` · `GET /api/v1/jobs/{id}` · `POST /api/v1/jobs/{id}/cancel`. Errors: 422 `validation_error`, 404 `job_not_found`, 429 `queue_full`, 413 `payload_too_large`. The `Job` schema is in `packages/schemas/geo-contracts.schema.json`.
