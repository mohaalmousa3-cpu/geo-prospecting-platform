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


def test_backend_has_no_analysis_modules_or_imports() -> None:
    """Phase 2 scope: AOI input only. No analysis, scoring or Earth Engine code in the backend."""
    banned_names = ("thermal", "prospectiv", "void", "geophysic", "scoring", "score", "earth_engine", "ee_")
    for f in py_files("apps/backend/src"):
        assert not any(w in f.stem.lower() for w in banned_names), f
        assert not {"ee", "earthengine", "geemap", "sklearn", "rasterio", "scipy"} & imported_roots(f), f


# --- Phase 3a: geo_connectors boundaries (ADR-0014, plan T8) ---
# No network-capable or raster modules may be imported by the connectors package. Importing `geo_connectors`
# (or `rasterio`, an HTTP client, `socket`, `ssl`, `urllib*`, `http*`) from the wrong place is a boundary violation.
CONNECTOR_BANNED = {
    "socket", "ssl", "http", "urllib", "urllib3", "httpx", "requests", "aiohttp", "httplib2", "ftplib",
    "smtplib", "telnetlib", "xmlrpc", "websockets", "pystac_client", "boto3", "rasterio", "ee", "earthengine",
}  # fmt: skip
CONNECTOR_ALLOWED_THIRD_PARTY = {"geo_common"}  # the only non-stdlib import root geo_connectors may use


def test_backend_runner_and_common_do_not_import_connectors() -> None:
    for rel in ("apps/backend/src", "workers/runner/src", "packages/pycommon/src"):
        for f in py_files(rel):
            assert "geo_connectors" not in imported_roots(f), f


def test_connectors_import_neither_backend_nor_runner() -> None:
    for f in py_files("workers/connectors/src"):
        assert not {"app", "runner"} & imported_roots(f), f


def test_connectors_import_no_network_http_or_raster_modules() -> None:
    for f in py_files("workers/connectors/src"):
        assert not CONNECTOR_BANNED & imported_roots(f), (f, CONNECTOR_BANNED & imported_roots(f))


def test_connectors_use_only_stdlib_and_geo_common() -> None:
    import sys

    stdlib = set(sys.stdlib_module_names)
    for f in py_files("workers/connectors/src"):
        extra = {r for r in imported_roots(f) if r not in stdlib and r != "geo_connectors"}
        assert extra <= CONNECTOR_ALLOWED_THIRD_PARTY, (f, extra)


def test_connectors_declare_no_third_party_dependency() -> None:
    import tomllib

    doc = tomllib.loads((ROOT / "workers/connectors/pyproject.toml").read_text())
    assert doc["project"]["dependencies"] == ["geo-common"]


def test_connectors_have_no_analysis_modules() -> None:
    for f in py_files("workers/connectors/src"):
        assert not any(w in f.stem.lower() for w in ANALYSIS_WORDS), f
