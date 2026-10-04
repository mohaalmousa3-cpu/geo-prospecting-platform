# Shared Schemas

Single source of truth for API/worker contracts: `geo-contracts.schema.json` (JSON Schema draft-07).

Generated artefacts (committed; CI fails on drift):
- Pydantic models → `packages/pycommon/src/geo_common/models/_generated.py`
- Packaged schema copy (runtime validation) → `packages/pycommon/src/geo_common/models/geo-contracts.schema.json`
- TypeScript types → `apps/frontend/src/types/contracts.ts`

Regenerate with `make schemas`; verify with `make schemas-check`.

Rules enforced by the schema (ADR-0009/0010): confidence, uncertainty, explanation (with ≥1 limitation), ≥1 source, provenance, disclaimer, `validation_status` (only `unvalidated`), `calibration_status`, `engine_status` are all required; no `confirmed_*` kinds; `depth` requires a geophysics/verification basis and disclaimer D-2; `deposit_model` requires `applicability`.
