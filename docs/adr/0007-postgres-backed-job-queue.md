# ADR-0007: Minimal queue — PostgreSQL-backed jobs, no Redis in V1

- **Status:** Accepted (recommendation requested by owner: "simplest reliable option for V1")
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 7), recommendation by Claude

## Context
V1 needs a handful of long-running (minutes), low-volume jobs on a single machine. PostgreSQL is already required and already holds job state and results.

## Options considered
| Option | Extra services | Verdict |
|---|---|---|
| **PostgreSQL-backed queue** (`job` table, `SELECT … FOR UPDATE SKIP LOCKED`) | none | **Chosen** |
| RQ (+Redis/Valkey) | Redis | Simple and mature, but adds a stateful service and a dual-write (DB row + Redis entry) consistency problem; Redis licence needs checking |
| arq / Dramatiq | Redis | Same extra service; no benefit at V1 scale |
| Celery (+broker) | broker + often result backend | Most capable, most complex; overkill |
| Postgres queue library (e.g. procrastinate) | none | Viable alternative; adds a dependency whose maturity/fit would need verifying. Keep as fallback to a hand-rolled claim loop |

## Decision
Use the existing `job` table as the queue.
- **Enqueue** = insert a row with `status='queued'` in the same transaction as any related writes (no dual-write).
- **Claim** = single statement: `UPDATE job SET status='running', locked_by=…, lease_expires_at=now()+lease WHERE id = (SELECT id FROM job WHERE status='queued' ORDER BY priority, created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING …`.
- **Worker** polls (default every 2 s), heartbeats to extend the lease, and runs the engine in a **child process** so a hard timeout can kill it.
- **Recovery:** jobs whose lease expired return to `queued` (up to `max_attempts`), else `failed` with reason.
- **Statuses (DB):** `queued`, `running`, `succeeded`, `failed`, `cancelled`, `insufficient_data`. (`created`/`validated` occur synchronously in the API before insert.)
- **Concurrency:** `WORKER_CONCURRENCY=1` default; `MAX_QUEUED_JOBS` enforced at enqueue.
- Hidden behind a `JobQueue` interface (`enqueue`, `claim`, `heartbeat`, `complete`, `fail`, `cancel`) so RQ/Celery can replace it without touching engines.

## Consequences
- We own ~150 lines of claim/lease/retry logic; it must be covered by integration tests (concurrent claim, crash recovery, timeout, cancel). This is the main reliability risk and is mitigated by tests, not by hope.
- Polling adds ≤ a few seconds latency — irrelevant for this workload.
- No Redis in Compose/`.env.example`; the earlier Redis-vs-Valkey question is closed for V1.
- Not suitable for high throughput or many workers across hosts.

## Revisit when
Sustained concurrency > ~a few workers, sub-second dispatch needed, or multi-host deployment (then evaluate RQ/Celery via a new ADR).
