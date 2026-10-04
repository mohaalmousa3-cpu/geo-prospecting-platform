# ADR-0009: Strict scientific naming; confidence and uncertainty are mandatory

- **Status:** Accepted (reaffirms and binds Phase 0 rules)
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 9)

## Decision
1. **Naming:** identifiers, schema fields, API routes, DB columns, UI strings, report text and file names use only calibrated terms: `*_prospectivity_score`, `*_evidence_score`, `thermal_anomaly`, `target_candidate`. Forbidden stems: `found`, `detected`, `confirmed`, `discovered`, `proven`, `deposit` (as a result), `cave`/`void` (as a detection result), `reserve`, `grade`, `tonnage`.
2. **Mandatory envelope:** every layer/target serialised by the API contains `confidence`, `uncertainty`, `explanation`, `sources`, `provenance`, `disclaimer_id`, `validation_status`. The API **must refuse to serialise** an object missing any of them (error, not default).
3. **Confidence** is categorical (`low|moderate|high`) with a stated basis. **Uncertainty** is quantitative with method named, or `not_quantified` + reason. Neither may be defaulted to a flattering value.
4. **Scores are relative and uncalibrated** unless a documented calibration against independent validation data exists; the field `calibration_status` ∈ {`uncalibrated`, `calibrated`} is mandatory, default `uncalibrated`.
5. **Engine maturity:** `engine_status` ∈ {`experimental`, `validated`}; all engines start `experimental`.
6. **Enforcement:** schema validation (Phase 1), forbidden-term scan test over source, fixtures and docs (Phase 1), envelope-completeness tests per engine (each phase).

## Consequences
- Slightly verbose payloads; accepted.
- The forbidden-term scanner needs an allow-list for this documentation (docs may discuss forbidden terms); scanner scope is defined in the Phase 1 plan.
- Supersedes nothing; complements `docs/scientific-constraints.md`.
