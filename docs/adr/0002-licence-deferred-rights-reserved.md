# ADR-0002: No open-source licence yet; internal "all rights reserved"

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 2)

## Context
Candidate dependencies include copyleft licences (e.g. EUPL-1.2, GPL-3.0; unverified, see `docs/dependency-strategy.md`). The repository licence interacts with how they are integrated. The owner does not want to commit to an open-source licence now.

## Decision
- Keep the placeholder `LICENSE` (rights reserved, no grant of use). No final open-source licence is selected.
- Do not vendor or copy third-party source into the repository.
- Integrate copyleft tools only as **separate processes / separate worker images** communicating through files, CLI or the job queue, and only after the dependency checklist is completed.
- Maintain `docs/third-party-licences.md` from Phase 1 (name, version, licence, usage mode, verification date).

## Consequences
- Internal use of copyleft tools is generally less constrained than distribution, but **any distribution, SaaS exposure to third parties, or publication changes the analysis** (confidence: *guess* regarding network-use clauses of EUPL/AGPL-type licences; needs qualified legal review before any external exposure).
- Adding a copyleft dependency still requires explicit owner approval (CLAUDE.md §6).
- This ADR is not legal advice.

## Revisit when
The repository is made public, the platform is hosted for others, or a binary/image is distributed.
