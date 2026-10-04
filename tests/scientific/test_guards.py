"""Scientific-guard tests (P1-15): forbidden claims, repo policy, defaults."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from forbidden_terms import scan_repo, scan_text
from geo_common.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    return [ROOT / p for p in out if p and (ROOT / p).is_file()]


# --- the scanner itself must detect violations (deliberate-violation check) -----------------
@pytest.mark.parametrize(
    "line",
    [
        "gold_found = True",
        "label = 'Gold detected'",
        "<p>Confirmed gold at this site</p>",
        "cave_detected: bool",
        "void-confirmed",
        "def mark_confirmed_cavity(t): ...",
        "tonnage = 12",
        "deposit discovered",
    ],
)
def test_scanner_detects_violations(line: str) -> None:
    assert scan_text(line), line


@pytest.mark.parametrize(
    "line",
    [
        "job_not_found",
        "raise NotFoundError",
        "found = 1",
        "gold_prospectivity_score",
        "void_evidence_score",
        "thermal_anomaly",
        "unconfirmed hypothesis",
        "x = 1  # forbidden-term-ok gold_found",
    ],
)
def test_scanner_has_no_false_positives(line: str) -> None:
    assert scan_text(line) == []


def test_repo_contains_no_forbidden_claims() -> None:
    problems = scan_repo(ROOT, tracked_files())
    assert problems == [], "forbidden terms:\n" + "\n".join(problems)


# --- repo policy (ADR-0004/0005/0006/0007) ---------------------------------------------------
FORBIDDEN_PACKAGES = {
    "redis",
    "valkey",
    "minio",
    "boto3",
    "botocore",
    "s3fs",
    "celery",
    "kombu",
    "rq",
    "dramatiq",
    "arq",
    "passlib",
    "pyjwt",
    "python-jose",
    "authlib",
    "fastapi-users",
    "itsdangerous",
    "earthengine-api",
    "ee",
    "geemap",
}
FORBIDDEN_NPM = {
    "next-auth",
    "@auth/core",
    "jsonwebtoken",
    "passport",
    "ioredis",
    "redis",
    "cesium",  # 3D rendering is Phase 7
}


def test_python_lockfile_has_no_forbidden_packages() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    names = {p["name"].lower() for p in lock["package"]}
    assert not (names & FORBIDDEN_PACKAGES), names & FORBIDDEN_PACKAGES


def test_npm_lockfile_has_no_forbidden_packages() -> None:
    import json

    lock_path = ROOT / "apps/frontend/package-lock.json"
    if not lock_path.exists():
        pytest.skip("frontend not installed yet")
    pkgs = {k.split("node_modules/")[-1] for k in json.loads(lock_path.read_text())["packages"] if k}
    assert not (pkgs & FORBIDDEN_NPM), pkgs & FORBIDDEN_NPM


def test_optional_features_default_off() -> None:
    s = Settings(_env_file=None)
    assert (s.ENABLE_EARTH_ENGINE, s.ENABLE_INSAR_WORKER, s.ENABLE_GEMPY_WORKER) == (
        False,
        False,
        False,
    )
    env = (ROOT / ".env.example").read_text()
    for flag in ("ENABLE_EARTH_ENGINE", "ENABLE_INSAR_WORKER", "ENABLE_GEMPY_WORKER"):
        assert f"\n{flag}=false" in env


def test_env_example_has_no_real_secrets() -> None:
    env = (ROOT / ".env.example").read_text()
    assert not re.search(r"AKIA[0-9A-Z]{16}|-----BEGIN|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}", env)
    assert re.search(r"^POSTGRES_PASSWORD=change-me$", env, re.M)
    assert re.search(r"^NEXT_PUBLIC_CESIUM_ION_TOKEN=$", env, re.M)


def test_no_earth_engine_imports_in_source() -> None:
    for f in tracked_files():
        if f.suffix == ".py" and "tests" not in f.parts and "scientific" not in f.parts:
            text = f.read_text()
            assert not re.search(r"^\s*(import|from)\s+(ee|earthengine|geemap)\b", text, re.M), f


def test_compose_has_no_forbidden_services_and_binds_loopback() -> None:
    compose = ROOT / "infrastructure/docker/docker-compose.yml"
    if not compose.exists():
        pytest.skip("compose file not created yet")
    text = compose.read_text()
    assert not re.search(r"^\s{2}(redis|valkey|minio):", text, re.M)
    for m in re.finditer(r'^\s*-\s*"([^"]+:\d+:\d+)"', text, re.M):
        assert m.group(1).startswith("${BIND_HOST:-127.0.0.1}:"), m.group(1)
    assert not re.search(r"0\.0\.0\.0:\d+:\d+", text)  # never publish on all interfaces


def test_no_authentication_code_in_backend() -> None:
    for f in (ROOT / "apps/backend/src").rglob("*.py"):
        text = f.read_text().lower()
        for bad in ("oauth", "jwt", "bearer", "password_hash", "login"):
            assert bad not in text, (f, bad)


def test_compose_build_secret_default_is_tracked_and_empty() -> None:
    """CI failed once because `*.pem` is git-ignored and the empty default CA file was never committed."""
    f = ROOT / "infrastructure/docker/no-ca.crt"
    assert f.exists() and f.stat().st_size == 0
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(f)], cwd=ROOT, capture_output=True)
    assert tracked.returncode == 0, "infrastructure/docker/no-ca.crt must be committed (check .gitignore)"
