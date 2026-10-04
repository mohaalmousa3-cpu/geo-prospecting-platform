"""The dependency-audit gate (scripts/audit_deps.py): outcome classification and CI wiring.

A scanner/network/input failure must never read as "clean", findings must be reported as findings, and the CI
job must not hide failures (`|| true`, `continue-on-error`).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("audit_deps", ROOT / "scripts" / "audit_deps.py")
assert _spec and _spec.loader
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_deps"] = audit
_spec.loader.exec_module(audit)

PIP_CLEAN = json.dumps({"dependencies": [{"name": "a", "version": "1", "vulns": []}], "fixes": []})
PIP_VULN = json.dumps(
    {
        "dependencies": [
            {"name": "Bad", "version": "1.0", "vulns": [{"id": "PYSEC-1", "fix_versions": ["1.1"]}]},
            {"name": "ok", "version": "2", "vulns": []},
        ]
    }
)
PIP_SKIPPED = json.dumps(
    {"dependencies": [{"name": "x", "version": "1", "skip_reason": "not found on PyPI"}], "fixes": []}
)


def npm_report(total: int, vulns: dict | None = None, deps: int = 10) -> str:
    return json.dumps(
        {
            "auditReportVersion": 2,
            "vulnerabilities": vulns or {},
            "metadata": {"vulnerabilities": {"total": total}, "dependencies": {"total": deps}},
        }
    )


NPM_VULN = npm_report(
    1, {"braces": {"severity": "high", "range": "*", "isDirect": False, "via": ["x"], "fixAvailable": False}}
)


# ---------------------------------------------------------------- pip-audit: three outcomes
def test_pip_clean() -> None:
    r = audit.classify_pip_audit("p", 0, PIP_CLEAN)
    assert r.status == audit.CLEAN and r.audited == 1 and not r.findings


def test_pip_findings_even_with_nonzero_exit() -> None:
    r = audit.classify_pip_audit("p", 1, PIP_VULN)
    assert r.status == audit.FINDINGS and r.findings == ["Bad==1.0 PYSEC-1 fix=['1.1']"]
    assert set(r.by_package) == {"bad"}


@pytest.mark.parametrize(
    ("rc", "out"),
    [
        (1, ""),  # network/tool crash: no report
        (2, "Traceback (most recent call last): ..."),  # not JSON
        (0, "{}"),  # no "dependencies"
        (0, json.dumps({"dependencies": []})),  # empty input is not "clean"
        (0, PIP_SKIPPED),  # packages that could not be audited
        (1, PIP_CLEAN),  # non-zero exit without findings is not "clean"
    ],
)
def test_pip_scanner_failures_are_never_clean(rc: int, out: str) -> None:
    assert audit.classify_pip_audit("p", rc, out).status == audit.FAILURE


# ---------------------------------------------------------------- npm audit: three outcomes
def test_npm_clean() -> None:
    assert audit.classify_npm_audit("n", 0, npm_report(0)).status == audit.CLEAN


def test_npm_findings_with_exit_1() -> None:
    r = audit.classify_npm_audit("n", 1, NPM_VULN)
    assert r.status == audit.FINDINGS and set(r.by_package) == {"braces"}


@pytest.mark.parametrize(
    ("rc", "out"),
    [
        (
            1,
            json.dumps({"error": {"code": "ENOTFOUND", "summary": "request failed"}}),
        ),  # registry unreachable
        (1, ""),
        (1, "npm ERR! network"),
        (0, json.dumps({"vulnerabilities": {}})),  # no metadata
        (0, npm_report(0, deps=0)),  # empty input
        (1, npm_report(0)),  # non-zero exit without findings
    ],
)
def test_npm_scanner_failures_are_never_clean(rc: int, out: str) -> None:
    assert audit.classify_npm_audit("n", rc, out).status == audit.FAILURE


# ---------------------------------------------------------------- gate semantics
def _res(status: str) -> object:
    return audit.ScanResult("x", status)


def test_gate_exit_codes() -> None:
    c, f, x = audit.CLEAN, audit.FINDINGS, audit.FAILURE
    assert audit.gate_exit_code(_res(c), _res(c), [_res(c), _res(c)]) == 0
    assert audit.gate_exit_code(_res(f), _res(c), [_res(f)]) == 1  # python production findings fail
    assert audit.gate_exit_code(_res(c), _res(f), [_res(f)]) == 1  # npm production findings fail
    assert (
        audit.gate_exit_code(_res(c), _res(c), [_res(c), _res(f)]) == 0
    )  # dev-only findings: visible, not failing
    assert audit.gate_exit_code(_res(x), _res(c), []) == 2  # scanner failure
    assert audit.gate_exit_code(_res(f), _res(c), [_res(x)]) == 2  # failure takes precedence over findings
    assert audit.gate_exit_code(_res(c), _res(c), [_res(x)]) == 2  # a failed dev scan is also a failure


def test_dev_only_lists_findings_absent_from_production() -> None:
    prod = audit.classify_npm_audit("p", 1, NPM_VULN)
    other = npm_report(
        2,
        {
            "braces": {"severity": "high", "range": "*", "isDirect": False, "via": [], "fixAvailable": False},
            "lint-only": {
                "severity": "high",
                "range": "*",
                "isDirect": True,
                "via": [],
                "fixAvailable": False,
            },
        },
    )
    full = audit.classify_npm_audit("f", 1, other)
    lines = audit.dev_only(full, prod)
    assert len(lines) == 1 and lines[0].startswith("lint-only ")
    clean = audit.classify_npm_audit("p", 0, npm_report(0))
    assert len(audit.dev_only(full, clean)) == 2  # nothing in production: everything is dev-only


# ---------------------------------------------------------------- CI wiring
def _audit_job() -> str:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    start = text.index("\n  audit:")
    rest = text[start + 1 :]
    nxt = [i for i in (rest.find("\n  e2e:"), rest.find("\n  docker-build:")) if i > 0]
    return rest[: min(nxt)] if nxt else rest


def test_ci_audit_job_does_not_hide_failures() -> None:
    job = _audit_job()
    assert "scripts/audit_deps.py" in job
    assert "|| true" not in job and "continue-on-error" not in job
    assert "pip-audit --local" not in job  # that audited uvx's own environment, not the project's
