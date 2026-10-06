# geo_connectors (Phase 3a, fixtures-only)

Workspace package `geo-connectors` (ADR-0014). **Data access only**: no interpretation, scoring or analysis, and no scientific result is produced here. Records are catalogue metadata; assets it publishes are staged *inputs*.

Package surface (`src/geo_connectors/`):

* `contracts.py` — `Connector` (pure `fetch(FetchContext) -> FetchResult`; no database, storage or network I/O inside `fetch`), request/result/source types, `ConnectorMode`, the fetch-window flag used by the offline network guard.
* `registry.py` — connector registry and `resolve_connector(mode, name)`: `disabled` (default) → `ConnectorsDisabled`; `fixture` → the offline fixture connector; `live` → `LiveModeNotAvailable` (no live path exists).
* `fixture.py` + `fixtures/` — offline connector over two committed **synthetic** fixtures (`synthetic_catalog_v1.json`, `synthetic_catalog_empty_v1.json`).
* `handler.py` — `catalog_search(payload, context)`, the runner entry point (`geo_connectors.handler:catalog_search`, registered by import path): reads the job's AOI, runs the fixture connector, stages the file and publishes one `scene_catalog` asset with provenance through `geo_common.assets_pg`; zero matches → `insufficient_data`.
* `provenance.py` — `build_provenance_record` (pure; the record stored with each asset).
* `request_hash.py` — canonical, versioned `request_hash` (`v1:<sha256>`); idempotency of the publication request only, not result deduplication.
* `errors.py` — connector, mode, publication-busy (retryable) and publication-refused errors.
* `testing.py` — reusable contract checks for any connector (offline fixture harness).

Boundaries (tested in `tests/unit/test_architecture.py` and the connector tests): imports `geo_common` only; the backend and the runner never import it (the runner loads the handler by import-path string); no HTTP client, `socket`, `ssl`, `urllib*` or `rasterio`; no third-party dependency; no cache; no provider host, port or credential configuration. **No live network behaviour exists**; live slices are deferred (`docs/phase-3-plan.md` §8a). The worker image installs this package (`EXTRA_PACKAGE`); the backend image does not.
