# Decision note — `ON DELETE CASCADE` on `result.job_id` and `provenance.job_id`

**Status: awaiting the owner's decision. No schema change was made in CP4 and none will be made without separate explicit approval.**
Prepared 2026-10-06 (Phase 3a, CP4), as required by the owner's CP4 instruction. The application guard (`409 has_results`, ADR-0014 CP3 record) stays required whatever is decided.

## 1. Facts (verified on the CP4 schema, PostgreSQL 16)

| Fact | Evidence |
|---|---|
| The only `CASCADE` foreign keys in the schema are `result_job_id_fkey` and `provenance_job_id_fkey`; the other five (`aoi_project_id_fkey`, `job_aoi_project_fk`, `data_asset_aoi_project_fk`, `data_asset_job_fk`, `data_asset_provenance_fk`) are `RESTRICT`, immediate, validated | `pg_constraint` query on the migrated test database (`confdeltype`) |
| Today, raw `DELETE FROM job` silently removes the job's `result` and non-asset `provenance` rows | Experiment in a rolled-back transaction: 0 result and 0 provenance rows left. Also pinned by a characterisation test (`test_the_guard_is_per_target_and_the_schema_cascade_is_unchanged`) |
| Asset-owned rows are already protected at the database level: `data_asset_job_fk` and `data_asset_provenance_fk` are `RESTRICT` | CP3 migration tests (T-D13 extended) |
| No code writes `result` rows or result-side `provenance` today; the only application code that deletes jobs is `app.deletion`, which refuses with `has_results` first | `test_only_the_known_modules_write_or_delete_job_asset_and_provenance_rows` (policy-only check) |
| Plain `TRUNCATE job` is refused while `result` references it; `TRUNCATE job CASCADE` truncates `result` and `provenance` **whatever the delete action** | Same experiment, with the actions as they are today and with `RESTRICT` |
| Neither action stops `DELETE FROM result` itself, `DROP TABLE`, a superuser or a bad migration | PostgreSQL semantics; not a property of either option |

Confidence: **confirmed** for all rows above (observed, not inferred).

## 2. Options

| | **A — keep `CASCADE` + application guard** | **B — `RESTRICT` (future migration 0006)** | **C — mixed (`result` RESTRICT, `provenance` CASCADE)** |
|---|---|---|---|
| Protection if deletion bypasses the application | **None** for `result` and non-asset `provenance`: any raw `DELETE FROM job` removes them without error | Raw `DELETE FROM job` fails with `23503` while any `result` or `provenance` row references the job. Not covered: `TRUNCATE … CASCADE`, `DELETE FROM result`, DROP, superuser | As B for jobs that have results; a job **without** results loses its non-asset provenance silently (asset-owned provenance stays protected by its own RESTRICT keys) |
| Migration / compatibility | None | One migration, two `ALTER TABLE … DROP/ADD CONSTRAINT` statements. Tables are empty today, so the validation scan is trivial and the lock is brief. Reversible (downgrade restores `CASCADE`, no data loss). Code and tests that raw-delete jobs which have results (one characterisation test) must change. `23503` on these two constraints maps to the existing `409 still_referenced`; the introspection tests (which assert RESTRICT for the `job`/`aoi`/`data_asset` keys today) could then assert it for **every** foreign key in the schema | As B for `result`; keeps today's behaviour for `provenance`; needs a stated rule for which provenance may vanish — none exists today, and no discriminator column exists to define one |
| Deletion workflow consequences | AOI/project deletion: unchanged (`has_active_jobs` → `has_results` → `needs_cascade`/`project_not_empty`). Removing results by any other route needs no explicit step, which is the hazard | AOI/project deletion: unchanged, because the guard refuses first. Any future "delete a result/job" feature must delete `result` and `provenance` rows explicitly, then the job (needs its own ADR) | As B for results; provenance would go with its job |
| Effect on historical result retention | None as a rule; **retention depends on every future code path respecting the guard** | Retention is enforced by the schema for job deletion. Existing rows: none today, so nothing to migrate | As B for results; provenance without results is not retained |

## 3. Recommendation: **B**, before any writer exists

1. It removes the contradiction between the policy the owner recorded on 2026-10-06 and implemented as `has_results` (AOI/project deletion never removes scientific records; ADR-0014 CP3 record) and a schema that removes them silently when a job is deleted another way. Under A that policy lives in one module whose exclusivity is checked only by a policy test.
2. It costs almost nothing now (empty tables, metadata-only, reversible) and gets harder only once a result writer and a retention rule exist.
3. It changes no legitimate flow: the guard refuses first and returns the clearer `has_results`; the foreign key is the second line, not the first.
4. It makes the invariant uniform and testable: every foreign key is `RESTRICT` and immediate.

**Why not C:** nothing today needs provenance to disappear with its job (asset provenance is deleted explicitly and is RESTRICT-protected; no result-side writer exists), and there is no discriminator to say which provenance may vanish. I would only revisit C if a concrete diagnostic-provenance writer appears. **Why A remains acceptable** if the owner prefers zero schema change until Phase 5: the guard is tested, there are no writers, and the exposure is limited to raw SQL by the operator; the cost is that the gap must be reopened before the first writer is merged.

Limits of B, stated plainly: it does not make results immutable and does not protect against `TRUNCATE … CASCADE`, `DELETE FROM result`, dropping tables, or restoring an older backup.

## 4. Needed from the owner

Choose A, B or C (or defer with a trigger, e.g. "before the first `result` writer is merged"). If B or C is chosen, a separate instruction authorises migration 0006, its tests (up/down/up, introspection, bypass refusal, `still_referenced` mapping, characterisation test change) and the ADR/data-model edits. Until then the schema is unchanged and the guard is the only protection.
