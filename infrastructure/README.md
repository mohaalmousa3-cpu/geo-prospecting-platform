# Infrastructure

Docker, Compose and CI configuration (Phase 1, see `docs/phase-1-plan.md` P1-13/P1-16).

- Local Docker Compose is the default. Services: `postgis`, `backend`, `worker`, `frontend`.
- **No Redis, no MinIO** (ADR-0006, ADR-0007). Storage is a shared local volume.
- **No authentication** (ADR-0005): publish ports on `127.0.0.1` only; never expose publicly.
- No always-on paid cloud resources.
- `docker/` – Dockerfiles and compose files; `ci/` – CI helper scripts (workflows live in `.github/workflows/`).
