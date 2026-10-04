# Risk Register

Likelihood (L) / Impact (I): Low · Med · High. Review at each phase boundary. Owner = role, to be assigned.

| ID | Category | Risk | L | I | Mitigation | Trigger / Indicator |
|---|---|---|---|---|---|---|
| S-1 | Scientific | Remote-sensing signals are non-unique; outputs interpreted as proof | High | High | Mandatory language rules, envelope, disclaimers, guard tests, explanation with counter-evidence | Any UI/API string implying confirmation |
| S-2 | Scientific | Gold models mis-applied to wrong deposit type/climate/cover | High | High | Explicit deposit-type scope; flag out-of-scope AOIs; confidence reduction | AOI outside validated domain |
| S-3 | Scientific | Thermal anomalies dominated by confounders (albedo, moisture, slope, season) | High | High | Confounder normalisation, temporal persistence, capped confidence for single-date | Anomalies correlate with slope/aspect |
| S-4 | Scientific | Training data sparse/biased → overfit prospectivity | High | Med | Spatial CV, uncertainty maps, label experimental status | Large CV vs random-CV gap |
| S-5 | Scientific | Inversion non-uniqueness misread as ground truth (Phase 8) | Med | High | Show DOI, misfit, regularisation, warnings | Users citing sections as definitive |
| S-6 | Scientific | Invented thresholds/weights enter code | Med | High | `TODO(science-review)` convention, citations required, expert review | Magic numbers in PRs |
| L-1 | Licensing | Copyleft dependencies (EUPL/GPL/AGPL) constrain repo licence/distribution | High | High | Process isolation, licence ADR before Phase 1 code, `third-party-licences.md`, legal review | Dependency added without record |
| L-2 | Licensing | Data licences restrict use/redistribution (DEMs, geology surveys, cave inventories) | Med | High | Per-source licence metadata, no redistribution by default, respect restrictions | Source lacking licence field |
| L-3 | Licensing | Earth Engine / Cesium ion / tile providers terms (commercial use, quotas) | Med | Med | Optional + flagged; terms checked before enabling | Enabling without review |
| L-4 | Licensing | Redis/MinIO licence changes | Med | Low | ADR; consider Valkey / local volume | Upstream licence change |
| I-1 | Infrastructure | Heavy geo stacks (GDAL, pyGIMLi, MintPy) have fragile installs | High | Med | Separate pinned images, conda-lock, CI build of images | Image build failures |
| I-2 | Infrastructure | Dev/prod parity gaps; no production target chosen | Med | Med | Compose-first, ADR for deployment, avoid managed-service lock-in | — |
| I-3 | Infrastructure | Disk/RAM exhaustion from rasters | Med | High | Quotas, AOI limits, cleanup jobs, COG/windowed reads | Disk alarms |
| D-1 | Data availability | Cloud cover/gaps → no usable scenes | High | Med | `insufficient_data` state, date-window widening with disclosure | Zero valid scenes |
| D-2 | Data availability | Upstream API changes/outages/quota limits | Med | Med | Connector abstraction, caching, fixtures, retries | Connector errors |
| D-3 | Data availability | Poor geology/occurrence coverage in many regions | High | High | Show coverage/confidence honestly; allow user-supplied data | Sparse layers |
| D-4 | Data availability | Coarse resolution cannot resolve small voids | High | High | State resolution limits in explanations | Targets smaller than pixel |
| F-1 | False positive / false certainty | UI visual design (hot colours, rankings) conveys certainty | High | High | Neutral palettes, uncertainty overlays, calibrated language, "uncalibrated" labels | User feedback, UX review |
| F-2 | False positive / false certainty | Ranked list of N targets implies top-ranked are real | High | High | Show rank as relative; show confidence next to rank; threshold for "no credible targets" | — |
| F-3 | False positive / false certainty | Safety: users enter/excavate suspected voids | Low | High | Safety disclaimer, no guidance, emphasise verification | — |
| F-4 | False positive / false certainty | Depth inferred or implied from surface data | Med | High | Depth gating by schema; tests | Any depth field without basis |
| U-1 | UX | Overload of layers/parameters for non-experts | Med | Med | Sensible defaults, progressive disclosure, glossary | User confusion |
| U-2 | UX | Long jobs with unclear status | Med | Med | Status, ETA ranges, cancel, partial results | Support questions |
| U-3 | UX | Upload errors opaque | Med | Low | Specific validation messages | — |
| C-1 | Scaling | Large AOIs/time windows blow up compute/cost | High | High | Hard limits, tiling, estimates before run, quotas | Job runtimes > budget |
| C-2 | Scaling | Concurrent jobs starve workers | Med | Med | Queue priorities, per-engine concurrency, timeouts | Queue backlog |
| C-3 | Scaling | 3D rendering performance on large AOIs | Med | Med | LOD, tiling, resolution caps, perf budget | Frame-rate drops |
| P-1 | Project | Scope creep / building ahead of phase | High | Med | CLAUDE.md phase rules, backlog | Out-of-phase PRs |
| P-2 | Project | Lack of domain-expert review and validation data | High | High | Seek expert reviewer and benchmark sites early; engines stay *experimental* | No reviewer by Phase 4 |
| P-3 | Project | Security: hostile uploads, data leaks | Med | High | Upload hardening, size limits, no secrets in repo, auth ADR | — |
