.PHONY: sync lint typecheck test test-integration schemas schemas-check up down migrate guard

sync:
	uv sync --all-packages

lint:
	uv run ruff check . && uv run ruff format --check .

typecheck:
	uv run mypy packages/pycommon/src apps/backend/src workers/runner/src

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
