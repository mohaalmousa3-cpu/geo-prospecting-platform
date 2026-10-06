# Frontend

Next.js (TypeScript, React) + MapLibre GL (2D).

**Status (as of Phase 3a, fixtures-only, accepted 2026-10-06):** implemented — project and AOI workbench with a 2D map and an optional basemap (`none` by default, ADR-0013), a status page, the mandatory scientific disclaimer component, and types generated from `packages/schemas` (`src/types/contracts.ts`). The generated types include the job, asset and connector contracts of Phase 3a, **but there is no UI for jobs, assets, connectors or results**. **Not implemented:** 3D (CesiumJS is not installed; Phase 7), any result display, any scientific output. No UI work was part of Phase 3a.

Rules: consume generated types from `packages/schemas`; always render confidence, uncertainty and the scientific disclaimer for any future result; never use wording that implies confirmation (see `docs/scientific-constraints.md`). Browser smoke test: `make e2e` (CI job `e2e`).
