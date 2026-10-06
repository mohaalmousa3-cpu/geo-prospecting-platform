# Backend API

FastAPI service under `/api/v1` (local/private use only; no authentication in V1, ADR-0005).

**Status (as of Phase 3a, fixtures-only, accepted 2026-10-06):** implemented — health checks; projects; AOI input, validation and storage (ADR-0012/0013); jobs (`noop` and the fixtures-only `catalog_search`); staged-asset read/content/delete endpoints; a read-only `GET /connectors` capability description; AOI/project/asset deletion with the application guards (`app/deletion.py`). **Not implemented:** any scientific engine or result endpoint, live provider access, HTTP client, cache, authentication.

Routers (`src/app/api/`): `health`, `jobs`, `projects`, `aois` (including `GET /aois/{id}/assets`), `assets`, `connectors`. `catalog_search` creation (`app/catalog_jobs.py`) validates the request, checks `CONNECTOR_MODE` (`disabled` → 409, `live` → 501, `fixture` → queued) and derives the project from the AOI; details: [`docs/connectors.md`](../../docs/connectors.md).

Boundaries: no heavy compute in handlers; the backend never imports `workers/*` (`geo_connectors`, `runner`) — tested in `tests/unit/test_architecture.py`; persistence, queue and storage come from `packages/pycommon` (`geo_common`). Contracts: `packages/schemas`. Architecture: [`docs/architecture.md`](../../docs/architecture.md) §5a.
