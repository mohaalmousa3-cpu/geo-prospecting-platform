# geo_connectors (Phase 3a, fixtures-only)

Data-access connectors (ADR-0014). **Data access only**: no interpretation, scoring or analysis, and no scientific
result is produced here. Records are catalogue metadata.

* `contracts.py` — `Connector` (pure `fetch(FetchContext) -> FetchResult`), request/result types, `ConnectorMode`.
* `registry.py` — registry and `CONNECTOR_MODE` behaviour: `disabled` (default) → "connectors disabled";
  `fixture` → the offline fixture connector; `live` → explicitly "not available" in Phase 3a.
* `fixture.py` + `fixtures/` — offline connector over committed **synthetic** fixtures.
* `testing.py` — reusable contract checks for any connector (offline fixture harness).

Boundaries (tested in `tests/unit/test_architecture.py`): imports `geo_common` only; the backend never imports it;
no HTTP client, `socket`, `ssl`, `urllib*` or `rasterio`; no third-party dependency.
