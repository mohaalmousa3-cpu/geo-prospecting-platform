# ADR-0005: No authentication in V1 (local/private deployment only)

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 5)

## Context
V1 targets local development and private use. Authentication adds scope (identity, sessions, authorisation, per-user data isolation) not needed for the first phases.

## Decision
- V1 ships **without authentication or user accounts**.
- V1 is **not to be exposed to the public internet or untrusted networks.** Compose publishes services on `127.0.0.1` only by default.
- Compensating controls (mandatory even without auth): strict CORS allow-list, upload hardening, size/rate/compute limits (ADR-0008), request-size caps, no secrets in responses, no admin endpoints, structured logging without AOI contents at INFO level.
- All data is single-tenant. No `owner_id` column is added now (YAGNI); a later auth ADR will add it via migration.

## Consequences
- Anyone who can reach the API can create jobs, read all AOIs/results and consume compute. The deployment boundary is the only access control.
- Adding auth later will require a migration and a new ADR; avoid designs that hard-code single-tenancy in URLs.
- Risk P-3 is updated: any non-local deployment is blocked until auth + threat review exist.
- AOIs/uploads may be sensitive; they never leave the machine except for the external data requests required by connectors (which send AOI geometry/bounds to the provider — document per connector).

## Revisit when
Any shared, hosted, or multi-user deployment is planned.
