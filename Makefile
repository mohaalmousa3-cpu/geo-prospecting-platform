.PHONY: sync lint typecheck test test-integration schemas schemas-check up down migrate guard reconcile-assets

sync:
	uv sync --all-packages

lint:
	uv run ruff check . && uv run ruff format --check .

typecheck:
	uv run mypy packages/pycommon/src apps/backend/src workers/runner/src workers/connectors/src

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

guard:
	uv run pytest tests/scientific

schemas:
	./scripts/gen_schemas.sh

schemas-check:
	./scripts/gen_schemas.sh && git diff --exit-code -- packages/pycommon/src/geo_common/models apps/frontend/src/types

up:
	docker compose -f infrastructure/docker/docker-compose.yml --env-file .env up --build

down:
	docker compose -f infrastructure/docker/docker-compose.yml --env-file .env down

migrate:
	uv run python -m geo_common.migrate

.PHONY: licences frontend-check e2e ci ci-full
licences:
	uv run python scripts/licences.py

# Drain pending tombstones, then report (never delete or repair) unreferenced files and rows without a file.
reconcile-assets:
	uv run python scripts/reconcile_assets.py

frontend-check:
	cd apps/frontend && npm run lint && npm run typecheck && npm run format:check && npm test && npm run build

# Browser smoke test. Needs PostGIS and a database named $$E2E_POSTGRES_DB (default geo_e2e), plus either
# `npx playwright install chromium` or E2E_CHROMIUM_PATH=/path/to/chrome.
e2e:
	cd apps/frontend && npm run e2e

ci: lint typecheck test test-integration guard licences frontend-check schemas-check

# everything CI runs, including the browser smoke test
ci-full: ci e2e

.PHONY: audit
audit:
	python3 scripts/audit_deps.py
