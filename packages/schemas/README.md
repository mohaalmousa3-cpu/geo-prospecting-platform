# Shared Schemas

Single source of truth (JSON Schema / OpenAPI) for API and worker contracts. Pydantic and TypeScript types are generated from here (Phase 1).

Planned: `AOI`, `Job`, `Target`, `ResultEnvelope`, `Provenance`, `Evidence`, `Disclaimer`.

The `ResultEnvelope` must make confidence, uncertainty, explanation and sources **required**, and gate `depth` on `depth_basis`.
