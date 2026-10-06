#!/usr/bin/env bash
# Image smoke test (CI job "docker build smoke" and `make image-smoke`). Builds the images with the repository's
# compose file and checks, INSIDE them, that:
#   1. the worker image loads every registered handler and runs the fixture connector (no network, no database);
#   2. the backend image does NOT contain geo_connectors or runner (dependency direction, ADR-0011);
#   3. a stack in CONNECTOR_MODE=fixture executes a catalog_search job created through the API in the worker
#      image, publishes the fixture asset, and ends a zero-result request in insufficient_data.
# Fixtures only: no provider, no host, no credential, nothing published on the host. Uses its own compose project
# (geo-smoke) and removes it with its volumes afterwards. Needs a Docker daemon; honours PROXY_CA_BUNDLE
# (infrastructure/README.md) for TLS-intercepting proxies at build time.
set -euo pipefail
cd "$(dirname "$0")/.."

# Compose prefers variables of the calling shell over `--env-file` when it interpolates. CI exports
# POSTGRES_PASSWORD for other jobs, which initialised the database with that value while the services read the
# password from .env (CI run #18/#19: "password authentication failed"). The smoke stack must take ALL its
# settings from .env, so the caller's database variables are dropped.
unset POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_HOST POSTGRES_PORT

PROJECT=geo-smoke
COMPOSE=(docker compose -p "$PROJECT" -f infrastructure/docker/docker-compose.yml
         -f infrastructure/docker/docker-compose.smoke.yml --env-file .env)
created_env=0
if [ ! -f .env ]; then cp .env.example .env; created_env=1; fi
cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    "${COMPOSE[@]}" ps -a 2>&1 || true
    "${COMPOSE[@]}" logs --no-color --tail 80 2>&1 || true   # every service, incl. postgis and migrate
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  if [ "$created_env" = 1 ]; then rm -f .env; fi
  exit "$status"
}
trap cleanup EXIT

"${COMPOSE[@]}" build backend worker migrate

echo "== 1. worker image: registered handlers load, fixture connector runs (no network, no database)"
docker run --rm -i --network none "${PROJECT}-worker" python - < scripts/image_smoke_import.py

echo "== 2. backend image: geo_connectors and runner are absent"
docker run --rm --network none "${PROJECT}-backend" python -c \
  "import importlib.util as u; bad=[m for m in ('geo_connectors','runner') if u.find_spec(m)]; assert not bad, bad; print('absent: geo_connectors, runner')"

echo "== 3. fixture-mode stack: API-created job runs in the worker image"
"${COMPOSE[@]}" up -d --wait backend worker
"${COMPOSE[@]}" exec -T backend python - < scripts/image_smoke_client.py
echo "image smoke: OK"
