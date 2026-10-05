"""Every uv workspace member is an internal package for the licence register (scripts/licences.py).

A new first-party member that is missing from `WORKSPACE` would be reported as a third-party package with an
unknown licence (this happened for `geo-connectors` in Phase 3a). Only the first-party allowlist is covered here;
the approval logic and the register format are not touched by this test.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("licences", ROOT / "scripts" / "licences.py")
assert _spec and _spec.loader
licences = importlib.util.module_from_spec(_spec)
sys.modules["licences"] = licences
_spec.loader.exec_module(licences)


def _member_names() -> set[str]:
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())
    names = {root["project"]["name"]}
    for member in root["tool"]["uv"]["workspace"]["members"]:
        names.add(tomllib.loads((ROOT / member / "pyproject.toml").read_text())["project"]["name"])
    return {licences.norm(n) for n in names}


def test_every_workspace_member_is_in_the_internal_allowlist() -> None:
    assert _member_names() <= {licences.norm(n) for n in licences.WORKSPACE}


def test_geo_connectors_is_internal_not_a_third_party_row() -> None:
    assert "geo-connectors" in licences.WORKSPACE
    runtime, dev = licences.python_rows()
    listed = {licences.norm(name) for name, _, _ in runtime + dev}
    assert "geo-connectors" not in listed
    assert not any(lic == "UNKNOWN" for _, _, lic in runtime + dev)


def test_register_check_passes() -> None:
    assert licences.main() == 0
