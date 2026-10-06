# Infrastructure

Docker, Compose and CI configuration (Phase 1, see `docs/phase-1-plan.md` P1-13/P1-16).

- Local Docker Compose is the default. Services: `postgis`, `backend`, `worker`, `frontend`.
- **No Redis, no MinIO** (ADR-0006, ADR-0007). Storage is a shared local volume.
- **No authentication** (ADR-0005): publish ports on `127.0.0.1` only; never expose publicly.
- No always-on paid cloud resources.
- `docker/` – Dockerfiles and compose files; `ci/` – CI helper scripts (workflows live in `.github/workflows/`).
- **Image smoke test** (Phase 3a, fixtures only): `scripts/image_smoke.sh` / `make image-smoke` (CI job *docker build smoke*) builds the images and checks inside them that the worker image loads the registered handlers and runs an API-created `catalog_search` job in `CONNECTOR_MODE=fixture`, and that the backend image does not contain the connectors. It uses `docker/docker-compose.smoke.yml` (fixture mode, nothing published on the host) and its own compose project, removed afterwards. The worker image installs `geo-connectors` through the `EXTRA_PACKAGE` build argument; it adds no third-party package.

## Configuration source and local startup (Compose)
* **One source:** `./.env` at the repository root (copy `.env.example`; git-ignored). The `postgis` service and every Python service read the **same file** through `env_file`, so the database is initialised with exactly the credentials the services use. Variables exported in your shell do **not** reach the containers.
* **Start:** `cp .env.example .env` (once), then `make up` (= `docker compose -f infrastructure/docker/docker-compose.yml --env-file .env up --build`). `BIND_HOST` and the `NEXT_PUBLIC_*` build arguments are still read by Compose itself (shell, then `.env`); credentials never are.
* **Failure avoided:** Compose lets a variable exported in the calling shell override `--env-file` during interpolation. CI exports `POSTGRES_PASSWORD`, so the database was initialised with that value while `migrate` read `change-me` from `.env` (`28P01 password authentication failed`, CI runs #18/#19). Because PostgreSQL stores the password in the volume at first start, change `.env` **before** the first `make up`, or remove the volume (`make down` then `docker volume rm geo-prospecting_pgdata`) after changing it.
* **Readiness:** the `postgis` healthcheck is `pg_isready -h 127.0.0.1` (TCP, as the services connect), not the default unix-socket check, which answers about two seconds before TCP on a cold start.
* No network policy, egress rule or published port was changed by this.
