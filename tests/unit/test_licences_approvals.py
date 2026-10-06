"""F1-8: the narrow MPL-2.0 approval policy of scripts/licences.py (decision OA-0001) and the generated register.

Offline and deterministic: it reads the real lockfiles and the installed metadata of the project environment (the same
inputs `make licences` uses) and uses synthetic entries for the negative cases.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("licences", ROOT / "scripts" / "licences.py")
assert _spec and _spec.loader
lic = importlib.util.module_from_spec(_spec)
sys.modules["licences"] = lic
_spec.loader.exec_module(lic)

E = lic.Entry
A = lic.Approval
CERTIFI = E("pypi", "runtime", "certifi", "2026.7.22", "MPL-2.0")
APPROVAL = A("AP-T", "OA-0001", "pypi", "certifi", "2026.7.22", "MPL-2.0", "runtime", "test")


def date_free(text: str) -> str:
    return re.sub(r"\(verified [0-9-]+\)", "(verified X)", text)


# ------------------------------------------------------------------ the actual approvals
def test_the_four_oa_0001_mpl2_entries_are_approved_and_rendered_with_their_decision_reference() -> None:
    approvals = lic.load_approvals()
    assert [(a.name, a.version, a.scope, a.decision) for a in approvals] == [
        ("certifi", "2026.7.22", "runtime", "OA-0001"),
        ("pathspec", "1.1.1", "development", "OA-0001"),
        ("axe-core", "4.13.0", "development", "OA-0001"),
        ("lightningcss", "1.33.0", "development", "OA-0001"),
    ]
    text = lic.render()
    section = lic._section(text, "## Approved weak-copyleft entries")
    for a in approvals:
        assert f"| {a.name} | {a.version} | {a.licence} | {a.scope} | OA-0001 ({a.id}) |" in section
    assert "nothing here has been approved" not in text  # the former false blanket claim is gone
    for a in approvals:  # approved entries are no longer listed as pending
        assert f"| {a.name} | {a.version} | {a.licence} |\n" not in lic._section(
            text, "## Pending owner acknowledgement"
        )


def test_every_approval_matches_exactly_one_entry_of_the_current_lock_graph() -> None:
    present = lic.entries()
    for a in lic.load_approvals():
        hits = [e for e in present if lic.approval_for(e, [a]) is a]
        assert len(hits) == 1, a.id


def test_nothing_beyond_the_four_entries_is_approved() -> None:
    approvals = lic.load_approvals()
    approved = [e for e in lic.entries() if lic.approval_for(e, approvals)]
    assert {e.name for e in approved} == {"certifi", "pathspec", "axe-core", "lightningcss"}
    pending = {e.name for e in lic.pending(lic.entries(), approvals)}
    assert "lightningcss-darwin-arm64" in pending  # P-0001: undecided, still pending
    assert any(
        n.startswith("@img/sharp-libvips") for n in pending
    )  # LGPL entries are outside this MPL-2.0 policy
    text = lic.render()
    assert "| lightningcss-darwin-arm64 | 1.33.0 | MPL-2.0 |" in lic._section(
        text, "## Pending owner acknowledgement"
    )


# ------------------------------------------------------------------ an unapproved MPL-2.0 package is not accepted
@pytest.mark.parametrize(
    "entry",
    [
        E("pypi", "runtime", "newpkg", "1.0", "MPL-2.0"),  # a new MPL-2.0 package
        E("pypi", "runtime", "certifi", "2026.7.23", "MPL-2.0"),  # version bump
        E("pypi", "development", "certifi", "2026.7.22", "MPL-2.0"),  # other scope
        E("npm", "runtime", "certifi", "2026.7.22", "MPL-2.0"),  # other ecosystem
        E(
            "pypi", "runtime", "certifi", "2026.7.22", "Mozilla Public License 2.0 (MPL 2.0)"
        ),  # other licence string
        E("pypi", "runtime", "certifi", "2026.7.22", "MPL-2.0 AND MIT"),  # different expression
    ],
)
def test_a_near_miss_is_not_approved_and_is_flagged_if_not_listed_as_pending(entry: object) -> None:
    assert lic.approval_for(entry, [APPROVAL]) is None
    assert entry in lic.pending([entry], [APPROVAL])
    problems = lic.problems_for([entry], "# register without it", [APPROVAL])
    assert any("missing from register" in p or "not listed under pending" in p for p in problems)


def test_an_exact_match_is_approved_but_must_still_be_rendered_in_the_approved_section() -> None:
    assert lic.approval_for(CERTIFI, [APPROVAL]) is APPROVAL
    assert lic.pending([CERTIFI], [APPROVAL]) == []
    bare = "| certifi | 2026.7.22 | MPL-2.0 |"  # present as a row, but not in an approved section
    assert any(
        "not rendered in the approved section" in p for p in lic.problems_for([CERTIFI], bare, [APPROVAL])
    )
    ok = lic.render([APPROVAL])
    entries = [CERTIFI]
    assert lic.problems_for(entries, ok, [APPROVAL]) == []


def test_a_stale_approval_that_matches_nothing_fails_the_check() -> None:
    stale = A("AP-S", "OA-0001", "pypi", "gone", "1.0", "MPL-2.0", "runtime", "x")
    assert any("matches nothing" in p for p in lic.problems_for([CERTIFI], lic.render([APPROVAL]), [stale]))


def test_the_policy_cannot_approve_non_mpl_licences(tmp_path: Path) -> None:
    for bad in ("LGPL-3.0-or-later", "GPL-3.0-only", "Apache-2.0", "UNKNOWN"):
        f = tmp_path / "a.toml"
        f.write_text(
            f'[[approved]]\nid="X"\ndecision="OA-0001"\necosystem="pypi"\nname="p"\nversion="1"\nlicence="{bad}"\n'
            'scope="runtime"\nreason="r"\n'
        )
        with pytest.raises(ValueError, match="outside the MPL-2.0-only policy"):
            lic.load_approvals(f)
    f.write_text('[[approved]]\nid="X"\ndecision="OA-0001"\nname="p"\n')
    with pytest.raises(ValueError, match="missing or empty"):
        lic.load_approvals(f)


# ------------------------------------------------------------------ unchanged behaviour
@pytest.mark.parametrize("name", ["foo-gpl", "foo-agpl"])
def test_strong_copyleft_still_fails_even_with_an_approval_record_for_the_name(name: str) -> None:
    e = E("pypi", "runtime", name, "1.0", "GPL-3.0-only")
    forged = A("AP-X", "OA-0001", "pypi", name, "1.0", "MPL-2.0", "runtime", "x")
    assert lic.approval_for(e, [forged]) is None
    assert any(
        "strong copyleft" in p for p in lic.problems_for([e], f"| {name} | 1.0 | GPL-3.0-only |", [forged])
    )


def test_unknown_and_lgpl_behave_as_before() -> None:
    unknown = E("npm", "runtime", "mystery", "1.0", "UNKNOWN")
    assert any(
        "licence unknown" in p for p in lic.problems_for([unknown], "| mystery | 1.0 | UNKNOWN |", [APPROVAL])
    )
    lgpl = E("npm", "runtime", "libx", "1.0", "LGPL-3.0-or-later")
    assert lic.pending([lgpl], [APPROVAL]) == [lgpl]
    assert any(
        "not listed under pending" in p
        for p in lic.problems_for([lgpl], "| libx | 1.0 | LGPL-3.0-or-later |", [APPROVAL])
    )
    perm = E("pypi", "runtime", "ok", "1.0", "MIT")
    assert lic.problems_for([perm], "| ok | 1.0 | MIT |", []) == [] and lic.pending([perm], []) == []
    assert lic.APPROVED_COPYLEFT == {}


def test_the_committed_register_equals_a_fresh_render_apart_from_the_date_and_the_check_is_clean() -> None:
    """Generated-file drift: any change to approvals, locks or the template must be regenerated."""
    committed = (ROOT / "docs" / "third-party-licences.md").read_text(encoding="utf-8")
    assert date_free(lic.render()) == date_free(committed)
    assert lic.main() == 0
