"""Forbidden-term rules (ADR-0009/0010). Scanner config lives here; this file is excluded from scans.

A line may carry the marker `forbidden-term-ok` (e.g. a negative test example).
Documentation under ALLOWLIST_PREFIXES may *discuss* the forbidden terms.

Scope and limits (do not over-read a passing scan): this scans *source text* of files with the suffixes below
(including phrases split across lines or comment markers, but not across HTML/JSX tags), not the DOM a user sees at run time; it does not cover strings assembled
at run time, non-English text, or images/SVG; the patterns are phrase-shaped, so wording outside them passes.
"""

from __future__ import annotations

import re
from pathlib import Path

# Separators between the two words of a phrase: whitespace (incl. line breaks), `_`, `-`, and the comment/markdown
# decoration that can sit at a line break (`#`, `//`, `*`).
SEP = r"[\s_\-#*/]*"
# `mineral(is|iz)*` covers British and American spelling; "ore body" is treated like "ore".
MINERAL = r"mineral(?:is|iz)\w*"
ORE = rf"ore(?:{SEP}bod(?:y|ies))?"
SUBJECT = rf"(?:gold|deposit|{MINERAL}|{ORE})"
FEATURE = r"(?:cave|cavity|void)"
CLAIM_VERB = r"(?:found|detected|confirmed|discovered|proven|identified|located|encountered)"
PATTERNS: list[re.Pattern[str]] = [
    # "<gold|deposit|mineralis/ization|ore (body)> <claim verb | present>"
    re.compile(rf"(?<![A-Za-z]){SUBJECT}{SEP}(?:{CLAIM_VERB}|present)(?![A-Za-z])", re.I),
    # "<claim verb> <gold|cave|cavity|void|deposit|mineralisation|ore (body)>"
    re.compile(rf"(?<![A-Za-z]){CLAIM_VERB}{SEP}(?:{SUBJECT}|{FEATURE})(?![A-Za-z])", re.I),
    # "<cave|cavity|void> <claim verb | present>"
    re.compile(rf"(?<![A-Za-z]){FEATURE}{SEP}(?:{CLAIM_VERB}|present)(?![A-Za-z])", re.I),
    re.compile(
        r"(?<![A-Za-z])(ore_?grade|gold_?grade|tonnage|resource_?estimate|proven_?reserves?)(?![A-Za-z])",
        re.I,
    ),
]
MARKER = "forbidden-term-ok"
SCAN_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".md",
    ".html",
    ".css",
    ".sql",
    ".example",
}
ALLOWLIST_PREFIXES = ("docs/", "CLAUDE.md", "MASTER_SPEC.md", "TASKS.md", "tests/scientific/")
SKIP_PARTS = {
    "node_modules",
    ".venv",
    ".next",
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    "snapshots",
}
SKIP_NAMES = {"package-lock.json", "uv.lock"}


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, line) for each match; matches may span line breaks (reported at the first line).

    A match is ignored when any line it touches carries the `forbidden-term-ok` marker.
    """
    lines = text.splitlines()
    hits: dict[int, str] = {}
    for pat in PATTERNS:
        for m in pat.finditer(text):
            first = text.count("\n", 0, m.start()) + 1
            last = text.count("\n", 0, m.end()) + 1
            touched = lines[first - 1 : last]
            if any(MARKER in ln for ln in touched):
                continue
            hits.setdefault(first, lines[first - 1].strip() if first <= len(lines) else "")
    return sorted(hits.items())


def scan_repo(root: Path, files: list[Path]) -> list[str]:
    problems = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        if rel.startswith(ALLOWLIST_PREFIXES) or f.name in SKIP_NAMES:
            continue
        if f.suffix not in SCAN_SUFFIXES and f.name != ".env.example":
            continue
        if SKIP_PARTS & set(f.parts):
            continue
        for n, line in scan_text(f.read_text(encoding="utf-8", errors="ignore")):
            problems.append(f"{rel}:{n}: {line}")
    return problems
