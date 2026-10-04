"""Dependency direction (ADR-0011): backend → geo_common ← workers; no cross-imports."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_WORDS = ("thermal", "prospectivity", "void", "geophysic", "lst", "alteration")


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def py_files(rel: str) -> list[Path]:
    return [p for p in (ROOT / rel).rglob("*.py") if "__pycache__" not in p.parts]


def test_runner_does_not_import_backend() -> None:
    for f in py_files("workers/runner/src"):
        assert "app" not in imported_roots(f), f


def test_backend_does_not_import_workers() -> None:
    for f in py_files("apps/backend/src"):
        assert "runner" not in imported_roots(f), f


def test_geo_common_imports_neither_backend_nor_workers() -> None:
    for f in py_files("packages/pycommon/src"):
        assert not {"app", "runner"} & imported_roots(f), f


def test_geo_common_has_no_analysis_modules() -> None:
    names = [p.stem.lower() for p in py_files("packages/pycommon/src")]
    for n in names:
        assert not any(w in n for w in ANALYSIS_WORDS), n


def test_no_engine_code_in_phase_1() -> None:
    for engine in ("thermal", "gold_prospectivity", "void_evidence", "geophysics", "insar"):
        files = [p for p in (ROOT / "workers" / engine).rglob("*") if p.is_file()]
        assert [p.name for p in files] == ["README.md"], engine
