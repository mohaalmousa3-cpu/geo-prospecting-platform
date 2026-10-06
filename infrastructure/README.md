# Infrastructure

Docker, Compose and CI configuration (Phase 1, see `docs/phase-1-plan.md` P1-13/P1-16).

- Local Docker Compose is the default. Services: `postgis`, `backend`, `worker`, `frontend`.
- **No Redis, no MinIO** (ADR-0006, ADR-0007). Storage is a shared local volume.
- **No authentication** (ADR-0005): publish ports on `127.0.0.1` only; never expose publicly.
- No always-on paid cloud resources.
- `docker/` – Dockerfiles and compose files; `ci/` – CI helper scripts (workflows live in `.github/workflows/`).
- **Image smoke test** (Phase 3a, fixtures only): `scripts/image_smoke.sh` / `make image-smoke` (CI job *docker build smoke*) builds the images and checks inside them that the worker image loads the registered handlers and runs an API-created `catalog_search` job in `CONNECTOR_MODE=fixture`, and that the backend image does not contain the connectors. It uses `docker/docker-compose.smoke.yml` (fixture mode, nothing published on the host) and its own compose project, removed afterwards. The worker image installs `geo-connectors` through the `EXTRA_PACKAGE` build argument; it adds no third-party package.
