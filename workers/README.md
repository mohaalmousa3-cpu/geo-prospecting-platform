# Workers

Each engine is an isolated package (own dependencies / Docker image) exposing a typed `run(job_input) -> EngineResult`. Workers never import backend code. Third-party tools are wrapped in `adapters/`.

| Dir | Phase | Status |
|---|---|---|
| connectors | 3a | fixtures-only skeleton (data access only; no analysis); Phase 3b R8: offline egress policy and an unregistered urllib3 transport proof of concept, not reachable from any job |
| thermal | 4 | not started |
| gold_prospectivity | 5 | not started |
| void_evidence | 6 | not started |
| insar | 6 (optional) | not started |
| geophysics | 8 | not started |

Each engine MUST have a design doc (inputs, outputs, assumptions, limits, failure modes) before implementation.
