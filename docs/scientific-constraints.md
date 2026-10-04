# Scientific Constraints

Normative. Applies to code, API, UI, reports, tests, documentation and commit messages. Violations are defects.

## 1. Mandatory rules

1. **No confirmed gold from satellite/remote data alone.** Remote sensing can indicate alteration minerals, structures, lithological context. These are *indirect* and non-unique.
2. **No confirmed caves/voids from thermal or satellite data alone.** Thermal anomalies have many non-void causes (see §4). InSAR subsidence and terrain depressions are likewise indirect.
3. **Outputs are prospectivity/anomaly layers**, not detections.
4. **Subsurface depth** is shown only when derived from uploaded field geophysics or direct verification, with method, resolution limits and uncertainty. Surface-only data MUST NOT produce depth values, depth ranges, or "depth to target" labels.
5. **Confidence and uncertainty are mandatory** on every result.
6. **Explanation and source metadata are mandatory** on every target.
7. **No invented science**: thresholds, weights and coefficients must be sourced, derived from data, or flagged `TODO(science-review)`.
8. **Negative / insufficient-data outcomes must be reportable.**

## 2. Allowed vs forbidden language

| Forbidden | Allowed |
|---|---|
| "Gold found / detected / confirmed" | "Gold-related prospectivity", "target consistent with alteration signatures" |
| "Cave / void detected / confirmed" | "Void-related evidence score", "anomaly consistent with possible void; unverified" |
| "Depth: 12 m" (from surface data) | "Depth not available — requires field geophysics" |
| "Probability of gold = 87%" (uncalibrated) | "Relative prospectivity rank 3/50 (uncalibrated)" |
| "Safe to excavate/enter" | "Requires field verification and qualified safety assessment" |

Numeric scores are *relative rankings* unless calibration against independent validation data has been performed and documented; otherwise they MUST be labelled **uncalibrated**.

## 3. Confidence and uncertainty

- **Confidence** (qualitative: low / moderate / high): reflects data quality, number of independent concordant evidence lines, validation status, and coverage. Must state its basis.
- **Uncertainty** (quantitative where possible): propagated from inputs (e.g. LST retrieval error, DEM vertical error), model variance, or ensemble spread. If not quantifiable, state `not_quantified` and why.
- Confidence MUST be reduced for: single evidence line, cloud/snow/vegetation contamination, poor temporal coverage, extrapolation outside validated deposit type or climate, unvalidated engine status.
- Engines unvalidated against independent data are labelled **experimental** in UI and API.

## 4. Known non-uniqueness and failure modes (must be surfaced in explanations)

### Thermal
- Surface temperature reflects emissivity, albedo, soil moisture, vegetation, slope/aspect (solar loading), thermal inertia, time of acquisition, season, weather. Void-related thermal signatures (if any) are small and subtle relative to these effects.
- Landsat thermal resolution (~100 m native, resampled to 30 m) limits small-feature detection.
- Single-date anomalies are weak evidence; temporal persistence is required for any confidence above low.

### Gold prospectivity
- Models are deposit-type specific (orogenic, epithermal, porphyry-related, placer…). A model for one type is invalid for another.
- Alteration indices (e.g. iron oxides, clay/hydroxyl) are non-unique; barren alteration is common.
- Mapped occurrences are biased by access and past exploration; training labels are sparse and spatially clustered → spatial cross-validation required.
- Cover (vegetation, soil, sediment, regolith) can mask or mimic signals.

### Void evidence
- Terrain depressions, karst-like morphology, thermal and deformation signals each have multiple non-void explanations.
- Lithological context (soluble rocks, lava tubes, etc.) is a prerequisite for plausibility, not proof.
- InSAR requires coherence; unreliable over vegetation/snow/steep terrain.
- No entry, excavation or safety guidance is ever provided.

### Geophysics (Phase 8)
- Inversions are non-unique and regularisation-dependent; resistivity contrasts do not uniquely identify gold or voids.
- Depth of investigation is limited and must be displayed.
- GPR penetration depends strongly on ground conductivity.

## 5. Provenance requirements

For each result store: dataset IDs/versions/dates/licences, processing steps, parameters, software and dependency versions, code commit, run id, AOI hash, CRS.

## 6. Disclaimer text (canonical; referenced by `disclaimer_id`)

> **D-1 (all results):** This is a prospectivity/anomaly result derived from indirect data. It is not confirmation of mineralisation or of any cavity/void. Field verification by qualified professionals is required before any decision.
>
> **D-2 (depth):** Depth values are shown only for models derived from uploaded field geophysics or direct verification and carry method-dependent uncertainty and non-uniqueness.

## 7. Enforcement

- Schema validation rejects results missing confidence, uncertainty, explanation, sources.
- `tests/scientific/` contains: forbidden-term scans over UI strings/API fixtures/docs; envelope completeness tests; depth-gating tests.
- Code review checklist item: "Does this change make any output look more certain than the evidence?"
- Domain-expert (geologist/geophysicist) review is required before any engine leaves *experimental* status.
