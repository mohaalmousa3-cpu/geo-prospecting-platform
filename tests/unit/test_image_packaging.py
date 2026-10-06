"""Packaging policy for the Python images (policy-only static checks; the real check is scripts/image_smoke.sh).

The worker image must contain the fixtures-only connectors; the backend and migrate images must not
(dependency direction, ADR-0011). Nothing here builds an image.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()


def service_block(name: str) -> str:
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \w[\w-]*:\n|^\w)", COMPOSE, re.M | re.S)
    assert m, f"service {name} not found"
    return m.group(1)


def test_only_the_worker_image_installs_the_connectors() -> None:
    assert re.search(r"EXTRA_PACKAGE:\s*geo-connectors\b", service_block("worker"))
    for other in ("backend", "migrate"):
        assert "EXTRA_PACKAGE" not in service_block(other), other
        assert "geo-connectors" not in service_block(other), other


def test_dockerfile_installs_the_extra_workspace_member_without_dropping_the_first() -> None:
    text = (ROOT / "infrastructure/docker/python.Dockerfile").read_text()
    assert 'ARG EXTRA_PACKAGE=""' in text
    assert re.search(r'uv sync --frozen --no-dev --package "\$\{PACKAGE\}"', text)
    # `--inexact` keeps what the first sync installed; `--frozen` forbids touching the lockfile
    assert re.search(r'uv sync --frozen --no-dev --inexact --package "\$\{EXTRA_PACKAGE\}"', text)
    assert "pip install" in text and text.count("pip install") == 1  # still only `uv` itself via pip


def test_ci_runs_the_image_smoke_test_and_the_smoke_override_is_fixtures_only() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "./scripts/image_smoke.sh" in ci
    override = (ROOT / "infrastructure/docker/docker-compose.smoke.yml").read_text()
    assert set(re.findall(r"CONNECTOR_MODE:\s*(\w+)", override)) == {"fixture"}
    assert "ports: !reset []" in override  # nothing is published on the host by the smoke stack
    script = (ROOT / "scripts/image_smoke.sh").read_text()
    assert "--network none" in script  # the import check runs without any network


def test_postgis_takes_its_credentials_from_the_same_env_file_as_the_services() -> None:
    """Regression (CI #18/#19): `${POSTGRES_PASSWORD}` interpolation lets the caller's shell override --env-file."""
    block = service_block("postgis")
    assert re.search(r"^\s+env_file:\s*\.\./\.\./\.env\s*$", block, re.M)
    code = "\n".join(ln for ln in COMPOSE.splitlines() if not ln.lstrip().startswith("#"))
    # `$${VAR}` is the escaped, container-side form; a bare `${POSTGRES_*}` would be interpolated by Compose
    assert not re.search(r"(?<!\$)\$\{POSTGRES_", code), "no credential may be interpolated by Compose"
    assert re.search(r"^x-python-env:.*?env_file:\s*\.\./\.\./\.env", COMPOSE, re.M | re.S)


def test_postgis_health_is_checked_over_tcp_on_loopback() -> None:
    block = service_block("postgis")
    assert re.search(r"pg_isready -h 127\.0\.0\.1 -U \$\$\{POSTGRES_USER\} -d \$\$\{POSTGRES_DB\}", block)
    assert "service_healthy" in COMPOSE  # dependants wait for it
