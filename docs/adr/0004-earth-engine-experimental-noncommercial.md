# ADR-0004: Google Earth Engine allowed for experimental / non-commercial use only

- **Status:** Accepted (with conditions)
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 4)

## Context
Earth Engine (EE) offers server-side processing of large EO archives. Its free tier is restricted to non-commercial/research-type use (confidence: *likely*; current terms must be read from Google's official pages before first use). Mineral prospecting is frequently a commercial activity.

## Decision
EE may be used in early phases for **experimental, non-commercial** work, under these conditions:
1. **Optional and off by default:** `ENABLE_EARTH_ENGINE=false`. No EE import at module load when disabled.
2. **STAC/open sources remain the default path.** The platform must remain functional (possibly with reduced capability) without EE.
3. EE sits behind the connector interface (Phase 3); no engine imports EE directly.
4. **No credentials in the repo.** Service-account/user credentials live outside the repo; `.env.example` holds placeholders only.
5. **No billing-enabled / paid usage** without separate owner approval. Stay within free quotas; connector enforces request budgets.
6. Results derived via EE carry provenance `via: earth_engine` plus the EE asset IDs and dates.
7. **Use for client work, paid services, or commercial exploration decisions is NOT covered** by this approval. Before any such use: verify the then-current EE terms and obtain a commercial arrangement or remove EE from that workflow.
8. EE is not used in CI; tests use recorded fixtures.

## Consequences
- Phase 3 builds STAC first; EE connector is a flagged add-on, not a prerequisite for later phases.
- Any result relying on EE must remain reproducible or clearly labelled as depending on an external proprietary service.
- Risk L-3 stays open and is updated in the risk register.

## Revisit when
The platform's use becomes commercial, EE terms change, or quotas are hit.
