#!/usr/bin/env python3
"""Dependency audit gate (CI job `audit`; also runnable locally: `make audit`).

Audits the project's *locked* dependencies — never the tool's own environment:

* Python: ``uv export --frozen`` of ``uv.lock`` → ``pip-audit -r … --no-deps --disable-pip``.
  Two sets: production (``--no-dev``) and everything (all dependency groups).
* npm: ``npm audit --json`` against ``apps/frontend/package-lock.json``: production (``--omit=dev``) and full.

Every scan ends in exactly one of three outcomes, never blurred together:

* CLEAN            — the scan ran on a non-empty input and found nothing;
* FINDINGS         — the scan ran and reported vulnerabilities;
* SCANNER-FAILURE  — the scanner, network, registry or input failed (a failure is never read as "clean").

Exit codes: 0 = no failure and no *production* findings; 1 = production findings (Python or npm);
2 = at least one scanner failure (takes precedence over 1). Development-only findings never change the
exit code but are always printed in full (and as GitHub ``::warning`` annotations); nothing is suppressed
and there is no allow-list.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "frontend"
PIP_AUDIT = "pip-audit==2.10.1"  # pinned so the gate does not change under us; bump deliberately

CLEAN, FINDINGS, FAILURE = "CLEAN", "FINDINGS", "SCANNER-FAILURE"


@dataclass
class ScanResult:
    name: str
    status: str
    audited: int = 0
    findings: list[str] = field(default_factory=list)  # one line per vulnerable package/advisory
    by_package: dict[str, list[str]] = field(default_factory=dict)  # lower-cased name -> finding lines
    detail: str = ""


# --------------------------------------------------------------------------- classification (pure)
def classify_pip_audit(name: str, returncode: int, stdout: str) -> ScanResult:
    try:
        doc = json.loads(stdout)
        deps = doc["dependencies"]
        assert isinstance(deps, list)
    except (ValueError, KeyError, AssertionError, TypeError):
        return ScanResult(name, FAILURE, detail=f"pip-audit produced no parsable report (exit {returncode})")
    if not deps:
        return ScanResult(name, FAILURE, detail="pip-audit audited 0 packages (empty input)")
    skipped = [d.get("name", "?") for d in deps if "skip_reason" in d]
    res = ScanResult(name, CLEAN, audited=len(deps))
    for d in deps:
        for v in d.get("vulns", []):
            line = f"{d['name']}=={d['version']} {v.get('id')} fix={v.get('fix_versions') or 'none'}"
            res.by_package.setdefault(str(d["name"]).lower(), []).append(line)
            res.findings.append(line)
    if skipped:
        return ScanResult(
            name, FAILURE, audited=len(deps), detail=f"packages could not be audited: {', '.join(skipped)}"
        )
    if res.findings:
        res.status = FINDINGS
    elif returncode != 0:
        return ScanResult(
            name, FAILURE, audited=len(deps), detail=f"pip-audit exit {returncode} without findings"
        )
    return res


def classify_npm_audit(name: str, returncode: int, stdout: str) -> ScanResult:
    try:
        doc = json.loads(stdout)
    except ValueError:
        return ScanResult(name, FAILURE, detail=f"npm audit produced no parsable JSON (exit {returncode})")
    if not isinstance(doc, dict) or "error" in doc:
        err = doc.get("error") if isinstance(doc, dict) else doc
        return ScanResult(name, FAILURE, detail=f"npm audit error: {str(err)[:300]}")
    try:
        meta = doc["metadata"]
        total = int(meta["vulnerabilities"]["total"])
        audited = int(meta["dependencies"]["total"])
    except (KeyError, TypeError, ValueError):
        return ScanResult(name, FAILURE, detail="npm audit report has no metadata (unexpected format)")
    if audited == 0:
        return ScanResult(name, FAILURE, detail="npm audit audited 0 dependencies (empty input)")
    res = ScanResult(name, CLEAN, audited=audited)
    for pkg, v in (doc.get("vulnerabilities") or {}).items():
        via = [x if isinstance(x, str) else f"{x.get('title')} ({x.get('url')})" for x in v.get("via", [])]
        fix = v.get("fixAvailable")
        line = (
            f"{pkg} [{v.get('severity')}] range={v.get('range')} "
            f"{'direct' if v.get('isDirect') else 'transitive'} via={via} fixAvailable={fix}"
        )
        res.by_package.setdefault(pkg.lower(), []).append(line)
        res.findings.append(line)
    if total > 0 or res.findings:
        res.status = FINDINGS
    elif returncode != 0:
        return ScanResult(
            name, FAILURE, audited=audited, detail=f"npm audit exit {returncode} without findings"
        )
    return res


def gate_exit_code(py_prod: ScanResult, npm_prod: ScanResult, others: list[ScanResult]) -> int:
    """2 if any scan failed; else 1 if a production scan has findings; else 0 (dev findings never fail)."""
    if any(r.status == FAILURE for r in (py_prod, npm_prod, *others)):
        return 2
    if FINDINGS in (py_prod.status, npm_prod.status):
        return 1
    return 0


def dev_only(full: ScanResult, prod: ScanResult) -> list[str]:
    """Finding lines of the full scan for packages that have no finding in the production scan."""
    return [line for pkg, lines in full.by_package.items() if pkg not in prod.by_package for line in lines]


# --------------------------------------------------------------------------- running scanners
def _run(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str, str]:
    print(f"$ ({cwd.relative_to(ROOT) if cwd != ROOT else '.'}) {' '.join(cmd)}", flush=True)
    try:
        p = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    return p.returncode, p.stdout, p.stderr


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_python(label: str, export_flags: list[str], tmp: Path) -> ScanResult:
    req = tmp / f"requirements-{label}.txt"
    rc, out, err = _run(
        ["uv", "export", "--frozen", "--no-hashes", "--no-emit-workspace", "--all-packages", *export_flags],
        ROOT,
    )
    if rc != 0 or "==" not in out:
        return ScanResult(
            f"python/{label}", FAILURE, detail=f"uv export failed (exit {rc}): {err.strip()[:300]}"
        )
    req.write_text(out, encoding="utf-8")
    n = sum(1 for line in out.splitlines() if "==" in line and not line.startswith("#"))
    print(f"  input: {req.name}: {n} pinned requirements", flush=True)
    rc, out, err = _run(
        [
            "uvx",
            "--from",
            PIP_AUDIT,
            "pip-audit",
            "-r",
            str(req),
            "--no-deps",
            "--disable-pip",
            "--format",
            "json",
        ],
        ROOT,
    )
    res = classify_pip_audit(f"python/{label}", rc, out)
    if res.status == FAILURE and err.strip():
        res.detail += f" | stderr: {err.strip()[-300:]}"
    return res


def scan_npm(label: str, flags: list[str]) -> ScanResult:
    rc, out, err = _run(["npm", "audit", *flags, "--json"], FRONTEND)
    res = classify_npm_audit(f"npm/{label}", rc, out)
    if res.status == FAILURE and err.strip():
        res.detail += f" | stderr: {err.strip()[-300:]}"
    return res


def _report(r: ScanResult) -> None:
    print(f"[{r.status}] {r.name}: {r.audited} packages audited. {r.detail}".rstrip(), flush=True)
    for f in r.findings:
        print(f"    - {f}", flush=True)


def main() -> int:
    print("Dependency audit gate — locked inputs")
    for p in (ROOT / "uv.lock", FRONTEND / "package-lock.json"):
        print(f"  {p.relative_to(ROOT)} sha256={_sha(p)}")
    print(f"  scanner: {PIP_AUDIT}; npm {_run(['npm', '--version'], ROOT)[1].strip()}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        py_prod = scan_python("production", ["--no-dev"], tmp)
        py_all = scan_python("all-groups", ["--all-groups"], tmp)
        npm_prod = scan_npm("production", ["--omit=dev"])
        npm_all = scan_npm("all", [])
    for r in (py_prod, py_all, npm_prod, npm_all):
        _report(r)
    dev: list[tuple[str, str]] = []
    if py_all.status == FINDINGS:
        dev += [("python/dev-only", f) for f in dev_only(py_all, py_prod)]
    if npm_all.status == FINDINGS:
        dev += [("npm/dev-only", f) for f in dev_only(npm_all, npm_prod)]
    for scope, f in dev:
        print(f"::warning title=dev-only dependency finding ({scope})::{f}")
    code = gate_exit_code(py_prod, npm_prod, [py_all, npm_all])
    print(
        f"RESULT exit={code} "
        f"(python-prod={py_prod.status}, npm-prod={npm_prod.status}, "
        f"python-all={py_all.status}, npm-all={npm_all.status}, dev-only-findings={len(dev)})"
    )
    return code


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
