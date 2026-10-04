# ADR-0010: No "confirmed" gold or cavity language without field validation

- **Status:** Accepted (amended)
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 10); definitions of "field validation" proposed by Claude and approved by owner with stricter wording (see Amendment)

## Decision
1. No UI, API, report, log or doc may state or imply confirmed gold or a confirmed cavity/void unless a **field-validation record** exists for that specific target.
2. Remote-sensing and thermal outputs can never produce that status on their own. Geophysical anomalies (ERT/GPR/IP/magnetics) also do **not** by themselves confirm gold or a void; they remain "anomaly consistent with …".
3. Definition of field validation (approved):
   - **Gold:** assay results from an accredited laboratory on samples with documented location/chain of custody, **or** drill intersection logged and assayed by a qualified person.
   - **Cavity/void:** direct observation or survey by qualified persons (e.g. speleological/engineering survey), **or** drill/excavation intersection documented by a qualified person.
4. A field-validation record contains: target ID, method, date, performer/qualification, report/reference, location accuracy, result, and notes. Validated wording is scoped (e.g. "assay-confirmed gold at sample S-12"), never "deposit" or resource language.
5. **V1 behaviour:** the workflow for creating validation records is **not built**. Every target has `validation_status = "unvalidated"`; the schema permits no other value in V1. A later ADR must define the workflow before any other status is allowed.

## Amendment (2026-10-04, owner approval with stricter wording)
- **Geophysical anomalies, even when multiple methods agree, may only raise a target to a *high-confidence investigation priority*. They can never produce confirmed status.**
- **Confirmation requires direct verification or lab-backed evidence** (definitions in point 3 are approved on that basis).
- The permitted highest label derived from geophysics is therefore of the kind "high-confidence investigation priority", never "confirmed".

## Consequences
- Matches the Phase 0 rule and removes any ambiguity about geophysics.
- User-supplied "ground truth" (e.g. known occurrences) is used only as evidence/validation input to engines and is labelled user-supplied; it does not flip a target to validated.
- Safety: no entry/excavation guidance is ever provided.

