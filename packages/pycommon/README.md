# geo_common (`packages/pycommon`)

Shared Python runtime for the backend and the workers (ADR-0011): contracts, persistence, queue and storage abstractions, configuration and generic utilities. **No analysis logic.**

Modules (`src/geo_common/`):

* `config.py` — typed `Settings` (environment variables only; documented in `.env.example`), including the ADR-0008 provisional limits and `CONNECTOR_MODE`.
* `db.py`, `migrate.py`, `migrations/` — engine factory and Alembic migrations (`migrations/versions/0001`–`0006`; run with `python -m geo_common.migrate`). Migrations 0004 (job↔AOI/project linkage), 0005 (`data_asset`, `storage_tombstone`) and 0006 (`result`/`provenance` job foreign keys `RESTRICT`) are Phase 3a.
* `queue.py`, `queue_pg.py` — the `JobQueue` interface and its PostgreSQL implementation (ADR-0007), including AOI-bound `enqueue`.
* `storage.py` — the `StorageBackend` interface and `LocalStorage` (ADR-0006): traversal-safe keys, staged atomic writes under `.staging/`.
* `assets_pg.py` — staged-asset persistence: publication, reads, single-asset delete, tombstone drain and the report-only reconciliation.
* `transactions.py` — whole-transaction retry and SQLSTATE/constraint helpers.
* `envelope.py`, `models/` — result-envelope guard and models generated from `packages/schemas` (do not edit `_generated.py`).
* `logging_setup.py` — structured logging.

Tests: `packages/pycommon/tests/` (integration tests need PostGIS at `GEO_TEST_DATABASE_URL`).

**Does not own:** backend routing or API behaviour (`apps/backend`), worker orchestration (`workers/runner`), provider or connector integration (`workers/connectors`), scientific logic of any kind, network access of any kind.
