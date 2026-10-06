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


# Phase 3b R8 (owner decision 2026-10-06): exactly ONE module may import the evaluated HTTP client and `ssl`; it is an
# unregistered, unreachable proof of concept (see workers/connectors/tests/test_transport_urllib3_isolation.py).
TRANSPORT_POC = "transport_urllib3.py"
TRANSPORT_POC_ALLOWED_BANNED = {"urllib3", "ssl"}
CONNECTORS_THIRD_PARTY_DEPENDENCIES = ["geo-common", "urllib3==2.8.0"]


def test_connectors_import_no_network_http_or_raster_modules() -> None:
    for f in py_files("workers/connectors/src"):
        banned = CONNECTOR_BANNED & imported_roots(f)
        if f.name == TRANSPORT_POC:
            banned -= TRANSPORT_POC_ALLOWED_BANNED  # nothing else: no socket, http, requests, httpx, ...
        assert not banned, (f, banned)


def test_connectors_use_only_stdlib_and_geo_common() -> None:
    import sys

    stdlib = set(sys.stdlib_module_names)
    for f in py_files("workers/connectors/src"):
        extra = {r for r in imported_roots(f) if r not in stdlib and r != "geo_connectors"}
        allowed = CONNECTOR_ALLOWED_THIRD_PARTY | ({"urllib3"} if f.name == TRANSPORT_POC else set())
        assert extra <= allowed, (f, extra)


def test_connectors_declare_exactly_the_approved_dependencies() -> None:
    import tomllib

    doc = tomllib.loads((ROOT / "workers/connectors/pyproject.toml").read_text())
    assert doc["project"]["dependencies"] == CONNECTORS_THIRD_PARTY_DEPENDENCIES


def test_connectors_have_no_analysis_modules() -> None:
    for f in py_files("workers/connectors/src"):
        assert not any(w in f.stem.lower() for w in ANALYSIS_WORDS), f


# --- Phase 3a CP3: asset persistence module (geo_common.assets_pg) and runner boundaries ---
def test_assets_module_has_no_network_http_or_analysis_imports_and_stays_in_geo_common() -> None:
    f = ROOT / "packages/pycommon/src/geo_common/assets_pg.py"
    roots = imported_roots(f)
    assert not CONNECTOR_BANNED & roots, CONNECTOR_BANNED & roots
    assert not {"app", "runner", "geo_connectors", "fastapi", "starlette"} & roots  # dependency direction
    tree = ast.parse(f.read_text())
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    words: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef | ast.ClassDef):
            words.append(n.name)
        elif isinstance(n, ast.arg):
            words.append(n.arg)
        elif isinstance(n, ast.Name):
            words.append(n.id)
        elif isinstance(n, ast.Attribute):
            words.append(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings:
            words.append(n.value)  # SQL text, keys, messages: code, not documentation
    code = " ".join(words).lower()
    for word in ("confidence", "score", "probab", "prospectiv", "interpret", "uncertain"):
        assert word not in code, word  # assets are inputs: no scientific vocabulary in identifiers or SQL


def test_runner_registers_connector_handlers_by_import_path_only() -> None:
    for f in py_files("workers/runner/src"):
        assert "geo_connectors" not in imported_roots(f), f  # the string path is data, not an import
    handlers = (ROOT / "workers/runner/src/runner/handlers.py").read_text()
    assert '"geo_connectors.handler:catalog_search"' in handlers


def test_connector_handler_does_not_import_the_runner_or_the_backend() -> None:
    roots = imported_roots(ROOT / "workers/connectors/src/geo_connectors/handler.py")
    assert not {"runner", "app", "sqlalchemy"} & roots
