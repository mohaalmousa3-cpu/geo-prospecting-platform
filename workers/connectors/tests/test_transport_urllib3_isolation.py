"""The urllib3 transport proof of concept is unregistered, unreachable and the only user of the new dependency."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TRANSPORT = "transport_urllib3"
SRC_DIRS = ("workers/connectors/src", "apps/backend/src", "workers/runner/src", "packages/pycommon/src")


def _py(rel: str) -> list[Path]:
    return [p for p in (REPO / rel).rglob("*.py") if "__pycache__" not in p.parts]


def _roots(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def _references(path: Path, needle: str) -> bool:
    """True if the file imports `needle` or uses it in a non-docstring string literal (e.g. a dynamic import path)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(needle in a.name for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (
            needle in (node.module or "") or any(needle in a.name for a in node.names)
        ):
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            if needle in node.value:
                return True
    return False


def test_only_the_transport_module_imports_urllib3_or_ssl_in_any_source_tree() -> None:
    for rel in SRC_DIRS:
        for f in _py(rel):
            hits = {"urllib3", "ssl"} & _roots(f)
            if f.name == f"{TRANSPORT}.py":
                assert hits == {"urllib3", "ssl"}, hits
            else:
                assert not hits, (f, hits)


def test_the_transport_code_uses_no_environment_proxy_cookie_or_verification_bypass() -> None:
    f = REPO / f"workers/connectors/src/geo_connectors/{TRANSPORT}.py"
    banned_roots = {
        "socket",
        "http",
        "urllib",
        "httpx",
        "requests",
        "aiohttp",
        "httplib2",
        "asyncio",
        "certifi",
        "os",
    }
    assert not banned_roots & _roots(f), banned_roots & _roots(f)
    tree = ast.parse(f.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    forbidden = {
        "environ",
        "getenv",
        "CERT_NONE",
        "ProxyManager",
        "proxy_from_url",
        "PoolManager",
        "CookieJar",
        "cookies",
    }
    assert not forbidden & names, forbidden & names
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        for kw in call.keywords:
            if kw.arg == "assert_hostname":
                assert not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
            if kw.arg in ("verify", "check_hostname"):
                assert not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
            if kw.arg == "cert_reqs":
                assert isinstance(kw.value, ast.Constant) and kw.value.value == "CERT_REQUIRED"
            if kw.arg in ("redirect", "retries"):
                assert isinstance(kw.value, ast.Constant) and kw.value.value is False


def test_no_other_source_file_references_the_transport() -> None:
    for rel in SRC_DIRS:
        for f in _py(rel):
            if f.name == f"{TRANSPORT}.py":
                continue
            assert not _references(f, TRANSPORT), f
    for f in (REPO / "infrastructure").rglob("*"):
        if f.is_file() and f.suffix in (".yml", ".yaml", ".sh", "") and "Dockerfile" in f.name + f.suffix:
            assert TRANSPORT not in f.read_text(encoding="utf-8"), f


def test_registry_handler_and_runner_paths_do_not_load_urllib3_or_the_transport() -> None:
    script = textwrap.dedent(
        """
        import json, sys
        from geo_connectors import contracts, errors, fixture, handler, provenance, registry, request_hash
        try:
            registry.resolve_connector("live", "fixture")
        except errors.LiveModeNotAvailable:
            live = "LiveModeNotAvailable"
        print(json.dumps({"urllib3": "urllib3" in sys.modules,
                          "transport": "geo_connectors.transport_urllib3" in sys.modules,
                          "ssl": "ssl" in sys.modules, "live": live}))
        """
    )
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=True, cwd=REPO
    )
    doc = json.loads(p.stdout.strip().splitlines()[-1])
    assert doc["urllib3"] is False and doc["transport"] is False, doc
    assert doc["live"] == "LiveModeNotAvailable"


def test_the_registry_exposes_no_connector_named_after_a_transport_or_provider() -> None:
    from geo_connectors import registry

    text = Path(registry.__file__).read_text(encoding="utf-8").lower()
    assert "urllib3" not in text and "transport" not in text and "earth" not in text


def test_the_dependency_is_exactly_urllib3_2_8_0_in_the_connectors_package_only() -> None:
    manifests = {
        "workers/connectors": ["geo-common", "urllib3==2.8.0"],
    }
    for rel, deps in manifests.items():
        doc = tomllib.loads((REPO / rel / "pyproject.toml").read_text(encoding="utf-8"))
        assert doc["project"]["dependencies"] == deps
    for rel in ("apps/backend", "workers/runner", "packages/pycommon", "."):
        text = (REPO / rel / "pyproject.toml").read_text(encoding="utf-8")
        assert "urllib3" not in text, rel
    for banned in (
        "httpx",
        "certifi",
        "requests",
        "aiohttp",
    ):  # none may become a declared dependency of connectors
        assert banned not in (REPO / "workers/connectors/pyproject.toml").read_text(encoding="utf-8")


def test_the_lock_pins_urllib3_and_only_the_connectors_package_depends_on_it() -> None:
    lock = tomllib.loads((REPO / "uv.lock").read_text(encoding="utf-8"))
    pkgs = {p["name"]: p for p in lock["package"]}
    assert pkgs["urllib3"]["version"] == "2.8.0"
    assert (
        "dependencies" not in pkgs["urllib3"] or pkgs["urllib3"]["dependencies"] == []
    )  # no transitive packages
    users = sorted(
        n for n, p in pkgs.items() if any(d["name"] == "urllib3" for d in p.get("dependencies", []))
    )
    assert users == ["geo-connectors"], users
    root_dev = pkgs["geo-prospecting-platform"] if "geo-prospecting-platform" in pkgs else None
    if root_dev is not None:  # urllib3 must not be a direct dependency of the workspace root either
        assert "urllib3" not in json.dumps(root_dev.get("dependencies", []))


def test_the_worker_image_but_not_the_backend_image_installs_the_connectors_package() -> None:
    compose = (REPO / "infrastructure/docker/docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count("EXTRA_PACKAGE") == 1  # unchanged: only the worker image installs geo-connectors
    assert "urllib3" not in compose


@pytest.mark.parametrize("flag", ["APPROVED_FOR_EXECUTION"])
def test_the_fixed_query_approval_flag_is_untouched(flag: str) -> None:
    from geo_connectors import fixed_query

    assert getattr(fixed_query, flag) is False
