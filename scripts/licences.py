"""Third-party licence register: generate (`--write`) or check (default).

Reads licences from installed package metadata (Python) and package-lock.json (npm), so entries
are *verified from metadata*, not memory. Check mode fails when a locked dependency is missing
from docs/third-party-licences.md, and when a copyleft-looking licence is not explicitly approved.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "third-party-licences.md"
APPROVALS_FILE = ROOT / "docs" / "licence-acknowledgements.toml"
STRONG = re.compile(r"(?<![A-Za-z])(AGPL|GPL|EUPL|SSPL|CC-BY-SA)", re.I)
WEAK = re.compile(r"(?<![A-Za-z])(LGPL|MPL|EPL|CDDL)|Mozilla Public", re.I)
# Strong copyleft always fails. Weak copyleft (LGPL/MPL) must appear in the register's
# "Pending owner acknowledgement" section (generated) until the owner approves it (CLAUDE.md §6: copyleft needs
# owner approval). Two mechanisms, both owner-controlled:
#   * APPROVED_COPYLEFT — name-level approval of any version (empty; unchanged);
#   * `[[approved]]` records in docs/licence-acknowledgements.toml — the ONLY narrow policy for MPL-2.0 (F1-8,
#     decision OA-0001): one record per package, matched on ecosystem + name + exact version + exact licence string
#     + scope (runtime / development). Anything not matching exactly stays pending. Tooling never approves.
APPROVED_COPYLEFT: dict[str, str] = {}
MPL2 = re.compile(r"^(MPL-2\.0|Mozilla Public License 2\.0 \(MPL 2\.0\))$")
SECTIONS = ("runtime", "development")
ECOSYSTEMS = ("pypi", "npm")
_APPROVAL_FIELDS = ("id", "decision", "ecosystem", "name", "version", "licence", "scope", "reason")
WORKSPACE = {"geo-common", "geo-backend", "geo-runner", "geo-connectors", "geo-prospecting-platform"}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def py_licence(name: str) -> str:
    try:
        md = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "NOT INSTALLED (platform-specific dependency; licence not verified here)"
    expr = md.get("License-Expression")
    if expr:
        return expr
    lic = (md.get("License") or "").strip()
    if lic and len(lic) < 80 and "\n" not in lic:
        return lic
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if "License" in c]
    return "; ".join(classifiers) or "UNKNOWN"


def python_rows() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    pkgs = {norm(p["name"]): p for p in lock["package"]}

    def closure(roots: list[str]) -> set[str]:
        seen: set[str] = set()
        stack = [norm(r) for r in roots]
        while stack:
            n = stack.pop()
            if n in seen or n not in pkgs:
                continue
            seen.add(n)
            stack += [norm(d["name"]) for d in pkgs[n].get("dependencies", [])]
        return seen

    runtime = closure(["geo-backend", "geo-runner", "geo-connectors", "geo-common"]) - {
        norm(w) for w in WORKSPACE
    }
    dev = set(pkgs) - runtime - {norm(w) for w in WORKSPACE}
    row = lambda n: (pkgs[n]["name"], pkgs[n].get("version", "?"), py_licence(pkgs[n]["name"]))  # noqa: E731
    return [row(n) for n in sorted(runtime)], [row(n) for n in sorted(dev)]


def npm_rows() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    lock = json.loads((ROOT / "apps/frontend/package-lock.json").read_text())
    runtime, dev = [], []
    for path, info in lock["packages"].items():
        if not path:
            continue
        name = path.split("node_modules/")[-1]
        lic = info.get("license", "UNKNOWN")
        lic = lic if isinstance(lic, str) else json.dumps(lic)
        (dev if info.get("dev") or info.get("devOptional") else runtime).append((name, info["version"], lic))
    return sorted(set(runtime)), sorted(set(dev))


@dataclass(frozen=True)
class Entry:
    ecosystem: str
    scope: str
    name: str
    version: str
    licence: str


@dataclass(frozen=True)
class Approval:
    id: str
    decision: str
    ecosystem: str
    name: str
    version: str
    licence: str
    scope: str
    reason: str


def load_approvals(path: Path | None = None) -> list[Approval]:
    """`[[approved]]` records of the acknowledgements file. Raises ValueError on any malformed or out-of-policy
    record (policy: MPL-2.0 licence strings only; known ecosystem and scope; every field present)."""
    path = path or APPROVALS_FILE
    if not path.exists():
        return []
    out: list[Approval] = []
    for rec in tomllib.loads(path.read_text(encoding="utf-8")).get("approved", []):
        missing = [f for f in _APPROVAL_FIELDS if not isinstance(rec.get(f), str) or not rec[f].strip()]
        if missing:
            raise ValueError(f"approval {rec.get('id', '?')}: missing or empty fields {missing}")
        a = Approval(**{f: rec[f] for f in _APPROVAL_FIELDS})
        if not MPL2.fullmatch(a.licence):
            raise ValueError(f"approval {a.id}: licence {a.licence!r} is outside the MPL-2.0-only policy")
        if a.ecosystem not in ECOSYSTEMS or a.scope not in SECTIONS:
            raise ValueError(f"approval {a.id}: unknown ecosystem or scope")
        out.append(a)
    ids = [a.id for a in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate approval ids")
    return out


def entries() -> list[Entry]:
    pr, pd = python_rows()
    nr, nd = npm_rows()
    return [
        Entry(eco, scope, n, v, lic)
        for eco, scope, rows in (("pypi", "runtime", pr), ("pypi", "development", pd),
                                 ("npm", "runtime", nr), ("npm", "development", nd))
        for n, v, lic in rows
    ]  # fmt: skip


def approval_for(e: Entry, approvals: list[Approval]) -> Approval | None:
    """Exact match only: a different version, scope, ecosystem or licence string is NOT approved."""
    if not WEAK.search(e.licence) or STRONG.search(e.licence) or not MPL2.fullmatch(e.licence):
        return None
    for a in approvals:
        if (a.ecosystem, a.scope, norm(a.name), a.version, a.licence) == (
            e.ecosystem, e.scope, norm(e.name), e.version, e.licence,
        ):  # fmt: skip
            return a
    return None


def table(rows: list[tuple[str, str, str]]) -> str:
    return "\n".join(
        ["| Package | Version | Licence |", "|---|---|---|"]
        + [f"| {n} | {v} | {lic} |" for n, v, lic in rows]
    )


def pending(es: list[Entry], approvals: list[Approval]) -> list[Entry]:
    return [
        e for e in es
        if WEAK.search(e.licence) and e.name not in APPROVED_COPYLEFT and approval_for(e, approvals) is None
    ]  # fmt: skip


def approved_table(rows: list[tuple[Entry, Approval]]) -> str:
    return "\n".join(
        ["| Package | Version | Licence | Scope | Decision |", "|---|---|---|---|---|"]
        + [f"| {e.name} | {e.version} | {e.licence} | {e.scope} | {a.decision} ({a.id}) |" for e, a in rows]
    )


def render(approvals: list[Approval] | None = None) -> str:
    approvals = load_approvals() if approvals is None else approvals
    pr, pd = python_rows()
    nr, nd = npm_rows()
    es = entries()
    approved = [(e, a) for e in es if (a := approval_for(e, approvals))]
    pend = pending(es, approvals)
    approved_md = approved_table(approved) if approved else "_none_"
    pend_md = table([(e.name, e.version, e.licence) for e in pend]) if pend else "_none_"
    return f"""# Third-Party Licence Register

Generated by `scripts/licences.py --write` from installed package metadata and lockfiles
(verified {date.today().isoformat()}). Do not edit by hand. Not legal advice (ADR-0002).
Copyleft entries require explicit owner approval. Approvals are recorded per package in `[[approved]]` records of
`docs/licence-acknowledgements.toml` (policy: MPL-2.0 only; exact package, version, licence string and scope;
nothing is approved by tooling). Strong copyleft (GPL/AGPL/EUPL/SSPL) is blocked by the check.

## Approved weak-copyleft entries (MPL-2.0 only; owner decision OA-0001)
Acknowledgement recorded by the owner for the entries below **as they are present in the current lock graph**
(unmodified use; no vendored or modified source). It is not a licence-compliance finding, covers no other package,
version, licence or scope, and does not authorise adding any dependency (a new MPL-2.0 package needs a separate
review). Reasons per entry: `docs/licence-acknowledgements.toml`.

{approved_md}

## Pending owner acknowledgement (weak copyleft: LGPL/MPL)
Used unmodified as dependencies (no vendored or modified source). **Not approved**: no matching record in
`docs/licence-acknowledgements.toml` (this includes LGPL entries and the `lightningcss-<platform>` packages, which are
undecided there — P-0001). Listed so the owner can approve or veto.

{pend_md}

## Python — runtime (shipped in backend/worker images)
{table(pr)}

## Python — development tooling (not shipped)
{table(pd)}

## npm — runtime (frontend image)
{table(nr)}

## npm — development tooling (not shipped)
{table(nd)}

## Base images and services (not package-managed)
| Component | Used as | Licence (from upstream; re-verify on upgrade) |
|---|---|---|
| python:3.12-slim (Docker official image) | backend/worker base | Python Software Foundation licence + Debian package licences |
| node:22-slim (Docker official image) | frontend base | MIT (Node.js) + Debian package licences |
| postgis/postgis:16-3.4 | database service (separate container, not linked) | PostgreSQL licence; PostGIS GPL-2.0-or-later (separate process) |

Scientific tools (EIS Toolkit, MintPy, pyGIMLi, ResIPy, GPRPy, GemPy) are **not** dependencies yet; see `docs/dependency-strategy.md`.
"""


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    end = text.find("\n## ", start + len(heading))
    return text[start : end if end > 0 else len(text)]


def problems_for(es: list[Entry], text: str, approvals: list[Approval]) -> list[str]:
    problems = []
    approved_text = _section(text, "## Approved weak-copyleft entries")
    pending_text = _section(text, "## Pending owner acknowledgement")
    for e in es:
        if f"| {e.name} | {e.version} |" not in text:
            problems.append(f"{e.ecosystem}: {e.name} {e.version} missing from register")
        if STRONG.search(e.licence) and e.name not in APPROVED_COPYLEFT:
            problems.append(
                f"{e.ecosystem}: {e.name} strong copyleft licence '{e.licence}' lacks owner approval"
            )
        if e.licence == "UNKNOWN":
            problems.append(f"{e.ecosystem}: {e.name} licence unknown")
        if WEAK.search(e.licence) and e.name not in APPROVED_COPYLEFT:
            a = approval_for(e, approvals)
            if a is None:
                if f"| {e.name} | {e.version} | {e.licence} |" not in pending_text:
                    problems.append(
                        f"{e.ecosystem}: {e.name} weak copyleft not listed under pending acknowledgement"
                    )
            elif (
                f"| {e.name} | {e.version} | {e.licence} | {e.scope} | {a.decision} ({a.id}) |"
                not in approved_text
            ):
                problems.append(
                    f"{e.ecosystem}: {e.name} approved by {a.decision} but not rendered in the approved section"
                )
    present = {(e.ecosystem, e.scope, norm(e.name), e.version, e.licence) for e in es}
    for a in approvals:
        if (a.ecosystem, a.scope, norm(a.name), a.version, a.licence) not in present:
            problems.append(
                f"approval {a.id} ({a.name} {a.version}) matches nothing in the current lock graph"
            )
    return problems


def main() -> int:
    if "--write" in sys.argv:
        try:
            DOC.write_text(render(), encoding="utf-8")
        except ValueError as exc:
            print(f"approvals invalid: {exc}")
            return 1
        print(f"wrote {DOC}")
        return 0
    if not DOC.exists():
        print("register missing; run scripts/licences.py --write")
        return 1
    text = DOC.read_text(encoding="utf-8")
    try:
        approvals = load_approvals()
    except ValueError as exc:
        print(f"approvals invalid: {exc}")
        return 1
    problems = problems_for(entries(), text, approvals)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
