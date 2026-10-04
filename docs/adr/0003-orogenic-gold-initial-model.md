# ADR-0003: Phase 5 gold model is scoped to orogenic gold

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 3)

## Context
Gold prospectivity models are deposit-type specific (`docs/scientific-constraints.md` §4). A generic "gold" model would be scientifically invalid.

## Decision
The initial and only Phase 5 deposit model is **orogenic gold**. Other types (epithermal, porphyry-related, placer, Carlin-type, IOCG, etc.) are **out of scope** and must not be implied.

Orogenic-gold scope rules:
1. Output naming: `gold_prospectivity_score` with `deposit_model = "orogenic"` recorded in every result and in provenance.
2. **Applicability gate:** before scoring, the engine assesses whether the AOI geology is plausibly consistent with an orogenic setting using available geology/structure data. Outcomes: `applicable`, `not_applicable`, `applicability_unknown` (e.g. no geology coverage). `not_applicable` → no score is produced (`insufficient_data`/out-of-scope explanation). `applicability_unknown` → confidence capped at *low* and stated in the explanation.
3. Candidate evidence layers (to be fixed, justified and cited in the Phase 5 design doc and **reviewed by a domain expert**; no thresholds or weights may be invented): structural controls (proximity/density of faults and shear zones, lineaments), host-lithology context, hydrothermal-alteration proxies from multispectral/SWIR data where bedrock is exposed, geochemical and geophysical data where available, known-occurrence proximity (used carefully; biased).
4. Placer, supergene or transported-cover settings are explicitly **not modelled**; cover reduces confidence.
5. Validation uses spatial cross-validation against known orogenic occurrences; until completed the engine is labelled *experimental* and scores *uncalibrated*.

## Consequences
- Phase 5 design doc, evidence layers, and tests are orogenic-specific.
- Void and thermal engines are unaffected.
- Data-source selection for geology depends on the **target region** (open question, see `TASKS.md`).
- Supporting literature-based statements must be cited in the design doc; this ADR makes no quantitative claims.

## Revisit when
A second deposit type is requested (new ADR + separate model, never a parameter tweak of this one).
