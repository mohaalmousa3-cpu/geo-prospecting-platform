"""Forbidden-term rules (ADR-0009/0010). Scanner config lives here; this file is excluded from scans.

A line may carry the marker `forbidden-term-ok` (e.g. a negative test example).
Documentation under ALLOWLIST_PREFIXES may *discuss* the forbidden terms.
"""

from __future__ import annotations

import re
from pathlib import Path

SEP = r"[\s_\-]*"
PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        rf"(?<![A-Za-z])(gold|deposit|mineralis\w*|ore){SEP}(found|detected|confirmed|discovered|proven)(?![A-Za-z])",
        re.I,
    ),
    re.compile(
        rf"(?<![A-Za-z])(confirmed|detected|discovered|proven){SEP}(gold|cave|cavity|void|deposit|mineralis\w*)(?![A-Za-z])",
        re.I,
    ),
    re.compile(
        rf"(?<![A-Za-z])(cave|cavity|void){SEP}(found|detected|confirmed|discovered)(?![A-Za-z])",
        re.I,
    ),
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
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if MARKER in line:
            continue
        for pat in PATTERNS:
            if pat.search(line):
                hits.append((n, line.strip()))
                break
    return hits


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
