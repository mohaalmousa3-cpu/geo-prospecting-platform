# Migration 0006 — design note (owner option B, 2026-10-06)

Status: design for the Phase 3a closure checkpoint. Decision source: the owner chose option B in `phase-3a-cascade-decision-note.md`. The application guard (`409 has_results`) stays and is **not** replaced by anything below.

## 1. Affected constraints and target actions
| Constraint | Today | After 0006 |
|---|---|---|
| `result_job_id_fkey` (`result.job_id → job.id`) | `ON DELETE CASCADE` | `ON DELETE RESTRICT ON UPDATE RESTRICT` |
| `provenance_job_id_fkey` (`provenance.job_id → job.id`, column nullable since 0005) | `ON DELETE CASCADE` | `ON DELETE RESTRICT ON UPDATE RESTRICT` |

`RESTRICT` (not `NO ACTION`) matches every other foreign key of the schema; both are immediate because the constraints are not deferrable, so there is no behavioural difference here. After 0006 every foreign key in the schema is `RESTRICT` and non-deferrable.

## 2. Upgrade and downgrade
* **Upgrade:** per constraint, `ALTER TABLE … DROP CONSTRAINT …` then `ADD CONSTRAINT … FOREIGN KEY (job_id) REFERENCES job(id) ON DELETE RESTRICT ON UPDATE RESTRICT`, in the one migration transaction. Adding re-validates existing rows (a full scan; the tables are empty today and have no writer). No data changes.
* **Downgrade:** the reverse (back to `ON DELETE CASCADE`). It never deletes or alters rows, so it loses nothing; it is **truthful and safe**, but it deliberately re-opens the silent-cascade behaviour, and the migration says so in its docstring. It does not refuse on data.

## 3. Raw `DELETE` before and after
* Before: `DELETE FROM job WHERE id = …` silently removes that job's `result` and non-asset `provenance` rows.
* After: the same statement fails with `23503` (`result_job_id_fkey` or `provenance_job_id_fkey`) while any such row exists, and nothing is deleted. Rows must be removed explicitly first.

## 4. Interaction with the application guard
The guard runs first, inside the deletion transaction after the locks and before anything destructive, and answers `409 has_results`. The foreign key is the second line: if a code path ever reached the job `DELETE` with such rows present, the existing translation answers `409 still_referenced` (SQLSTATE `23503`) instead of removing them. FK actions are not a substitute for the guard (the guard also reports a precise reason and refuses before locking assets or writing tombstones).

## 5. Asset-owned provenance stays deletable
The explicit deletion path already deletes, in one transaction and in this order: assets → their provenance rows → jobs → AOIs (ADR-0014 §7.5; `app.deletion`). Under `RESTRICT` that order is what makes it work: an asset's provenance row (even one with `job_id` set) is deleted before the job. Direct tests: AOI and project deletion with job-bound and job-less assets still succeed and leave no provenance.

## 6. Administrative operations
`TRUNCATE … CASCADE`, `DROP TABLE`, a superuser, a bad migration or restoring an older backup are administrative destructive operations **outside** any application protection and outside what a foreign-key action can prevent; neither the old nor the new action stops `TRUNCATE job CASCADE`. `DELETE FROM result` itself is likewise not prevented.

## 7. Tests (direct)
Up/down/up with introspection (`confdeltype = 'r'` for both, validated, non-deferrable, enabled); raw `DELETE FROM job` is refused with `23503` for result-owning and provenance-owning jobs and nothing changes; without such rows it succeeds; downgrade restores `CASCADE` and the characterisation test shows the silent removal again; application deletion still returns `has_results` before any destructive step; asset deletion path removes asset provenance.
