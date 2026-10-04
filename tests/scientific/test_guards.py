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


# Regression: gaps found when the guard's coverage was analysed (reverse word order, other verbs, American
# spelling, "ore body", "present", phrases split across lines or comment markers).
@pytest.mark.parametrize(
    "text",
    [
        "found gold",
        "Found Gold at the site",
        "Cave identified",
        "void located",
        "cavity identified",
        "Mineralization confirmed",
        "mineralization detected",
        "mineralisation confirmed",
        "confirmed mineralization",
        "gold present",
        "ore body detected",
        "ore-body confirmed",
        "ore present",
        "identified deposit",
        "located void",
        "Gold\nfound",
        "cave\n    detected",
        "Confirmed\nvoid",
        "# gold\n# found",
        "// ore body\n// confirmed",
        "**Gold** found",
    ],
)
def test_scanner_regressions_are_detected(text: str) -> None:
    assert scan_text(text), text


def test_multiline_match_is_reported_at_its_first_line() -> None:
    assert [n for n, _ in scan_text("ok line\nGold\nfound here")] == [2]


@pytest.mark.parametrize(
    "text",
    [
        "gold = 1  # forbidden-term-ok gold_found",
        "gold\nfound  # forbidden-term-ok",  # marker on any touched line
        "mineralization potential",
        "mineral_occurrence",
        "Possible gold prospectivity",
        "unidentified deposit model",
        "ore model description",
        "cave and void features are not claims",
        "return void",
        "present_value",
        "not_located",
    ],
)
def test_scanner_regressions_have_no_false_positives(text: str) -> None:
    assert scan_text(text) == [], text


def test_scan_repo_honours_the_documentation_allowlist_and_scans_everything_else(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("The word 'gold found' is discussed here.\n")
    (tmp_path / "TASKS.md").write_text("never write: gold found\n")
    (tmp_path / "ui.tsx").write_text(
        "export const x = 'Mineralization\\nconfirmed';\n// ore body\n// detected\n"
    )
    files = [tmp_path / "docs" / "note.md", tmp_path / "TASKS.md", tmp_path / "ui.tsx"]
    problems = scan_repo(tmp_path, files)
    assert len(problems) == 1 and problems[0].startswith("ui.tsx:2"), problems


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


def test_ci_keeps_the_browser_smoke_test_job() -> None:
    """Two defects (MapLibre worker, CORS DELETE) only showed in a real browser; keep the job."""
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert re.search(r"^  e2e:\n", ci, re.M), "ci.yml must define an `e2e` job"
    assert "npm run e2e" in ci and "playwright install" in ci
    spec = (ROOT / "apps/frontend/e2e/smoke.e2e.ts").read_text()
    for step in ("create project", "create AOI", "delete AOI", "cascade", "connectivity"):
        assert step in spec, step
    assert "retries: 0" in (ROOT / "apps/frontend/playwright.config.ts").read_text()


def test_basemap_defaults_to_none_everywhere() -> None:
    s = Settings(_env_file=None)
    assert s.NEXT_PUBLIC_BASEMAP_PROVIDER == "none"
    assert re.search(r"^NEXT_PUBLIC_BASEMAP_PROVIDER=none$", (ROOT / ".env.example").read_text(), re.M)
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "NEXT_PUBLIC_BASEMAP_PROVIDER:-none}" in compose
    assert (
        "NEXT_PUBLIC_BASEMAP_PROVIDER=none"
        in (ROOT / "infrastructure/docker/frontend.Dockerfile").read_text()
    )
