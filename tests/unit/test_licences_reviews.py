"""`[[review]]` records of docs/licence-acknowledgements.toml must match the generated register (Phase 3b R8).

A review documents why a permissive package was accepted; it approves nothing and is not read by the generator.
This test makes a stale or widened review fail, and proves no approval was added for it.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("licences", ROOT / "scripts" / "licences.py")
assert _spec and _spec.loader
lic = importlib.util.module_from_spec(_spec)
sys.modules["licences"] = lic
_spec.loader.exec_module(lic)

DOC = tomllib.loads((ROOT / "docs/licence-acknowledgements.toml").read_text(encoding="utf-8"))
REQUIRED = {
    "id", "ecosystem", "package", "version", "licence", "scope", "decision", "decision_date", "decision_reference",
    "reason", "not_approved",
}  # fmt: skip


def test_there_is_a_review_for_urllib3_and_every_review_is_complete() -> None:
    reviews = DOC["review"]
    assert [r["id"] for r in reviews] == ["RV-0001"]
    for r in reviews:
        assert set(r) == REQUIRED, set(r) ^ REQUIRED
        assert all(r[k] for k in REQUIRED) and r["not_approved"]


def test_each_review_matches_the_generated_register_exactly() -> None:
    runtime, dev = lic.python_rows()
    rows = {"runtime": runtime, "development": dev}
    for r in DOC["review"]:
        assert r["ecosystem"] == "pypi"
        match = [x for x in rows[r["scope"]] if lic.norm(x[0]) == lic.norm(r["package"])]
        assert match, f"{r['package']} is not in the {r['scope']} register section"
        (_, version, licence) = match[0]
        assert (version, licence) == (r["version"], r["licence"])
        text = (ROOT / "docs/third-party-licences.md").read_text(encoding="utf-8")
        assert f"| {r['package']} | {r['version']} | {r['licence']} |" in text


def test_urllib3_is_a_runtime_package_because_the_worker_image_ships_geo_connectors() -> None:
    runtime, dev = lic.python_rows()
    assert ("urllib3", "2.8.0", "MIT") in runtime
    assert "urllib3" not in {lic.norm(n) for n, _, _ in dev}


def test_reviews_are_for_permissive_licences_and_add_no_approval() -> None:
    for r in DOC["review"]:
        assert not lic.STRONG.search(r["licence"]) and not lic.WEAK.search(r["licence"])
    assert not lic.APPROVED_COPYLEFT  # name-level approvals stay empty
    approvals = lic.load_approvals()
    assert sorted(a.name for a in approvals) == [
        "axe-core",
        "certifi",
        "lightningcss",
        "pathspec",
    ]  # unchanged
    assert not any(re.search("urllib3", a.name, re.I) for a in approvals)
