# ADR-0001: Repository stays private

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 1)

## Context
The project processes user-supplied AOIs and (later) field geophysics data, and builds on dependencies whose licences are not yet reviewed (see `docs/dependency-strategy.md`). Premature publication would expose that work and create licence-compliance questions.

## Decision
The repository `geo-prospecting-platform` remains **private**. No part of it is published, mirrored publicly or submitted to public package indexes.

## Consequences
- No external contributions are assumed; the contribution process stays internal.
- Data samples committed under `data/samples/` must still have their source licence recorded (private ≠ licence-free).
- GitHub Actions minutes, secret scanning and branch protection are those of the private plan; CI design must not assume unlimited minutes.
- Making the repository public later requires a new ADR, a licence decision (ADR-0002) and a full dependency/data-licence review.

## Revisit when
Publication, partnership sharing, or hosting for third parties is proposed.
