"""The egress policy is offline and unwired: no network-capable imports or calls, no reference from live paths."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "workers/connectors/src/geo_connectors"
MODULES = ("egress_policy.py", "fixed_query.py")
BANNED_ROOTS = {
    "socket", "ssl", "http", "urllib", "urllib3", "httpx", "requests", "aiohttp", "httplib2", "ftplib", "smtplib",
    "telnetlib", "xmlrpc", "websockets", "pystac_client", "boto3", "rasterio", "ee", "earthengine", "asyncio",
    "selectors", "select", "subprocess", "importlib", "ctypes", "os", "pathlib", "shutil", "tempfile", "certifi",
}  # fmt: skip
ALLOWED_ROOTS = {
    "__future__",
    "ipaddress",
    "math",
    "re",
    "collections",
    "dataclasses",
    "typing",
    "geo_connectors",
}
BANNED_NAME_CALLS = {"__import__", "eval", "exec", "open", "compile", "input", "breakpoint"}
BANNED_ATTR_CALLS = {"getaddrinfo", "gethostbyname", "create_connection", "urlopen", "connect", "socket",
                     "system", "popen", "run", "Popen", "import_module"}  # fmt: skip


def _tree(name: str) -> ast.Module:
    return ast.parse((SRC / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", MODULES)
def test_modules_import_only_pure_stdlib_and_no_network_api(name: str) -> None:
    roots: set[str] = set()
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module, "relative imports are not used here"
            roots.add(node.module.split(".")[0])
    assert not roots & BANNED_ROOTS, roots & BANNED_ROOTS
    assert roots <= ALLOWED_ROOTS, roots - ALLOWED_ROOTS


@pytest.mark.parametrize("name", MODULES)
def test_modules_call_no_network_io_or_dynamic_import_builtins(name: str) -> None:
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                assert fn.id not in BANNED_NAME_CALLS, (name, fn.id, node.lineno)
            elif isinstance(fn, ast.Attribute):
                assert fn.attr not in BANNED_ATTR_CALLS, (name, fn.attr, node.lineno)


def test_policy_modules_are_not_wired_into_any_live_path() -> None:
    names = ("egress_policy", "fixed_query")
    for f in (REPO / "workers/connectors/src").rglob("*.py"):
        if f.name in MODULES or "__pycache__" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        assert not any(n in text for n in names), f
    for rel in ("apps/backend/src", "workers/runner/src", "packages/pycommon/src"):
        for f in (REPO / rel).rglob("*.py"):
            assert not any(n in f.read_text(encoding="utf-8") for n in names), f


def test_registry_still_has_no_live_path() -> None:
    from geo_connectors.errors import LiveModeNotAvailable
    from geo_connectors.registry import resolve_connector

    with pytest.raises(LiveModeNotAvailable):
        resolve_connector("live", "fixture")


_SCRIPT = textwrap.dedent(
    """
    import json, sys
    events = []
    WATCH = ("socket.", "ssl.", "urllib.", "http.client", "subprocess.", "os.system", "open", "ctypes.")
    def hook(event, args):
        if event.startswith(WATCH) and event != "open":
            events.append(event)
    before = set(sys.modules)
    sys.addaudithook(hook)
    from geo_connectors import egress_policy as ep, fixed_query as fq
    calls = []
    def resolver(host, port):
        calls.append((host, port))
        return ["8.8.8.8"]
    allow = ep.EgressAllowlist.of([("catalog.example", 443)])
    b = ep.RequestBudget(3, 5, 10, 30, 1000, 1)
    v = ep.verify_url("https://catalog.example/v1/x", allow, resolver)
    ep.plan_pinned_request(v, b, requests_made=0)
    ep.validate_redirect("https://catalog.example/y", allowlist=allow, resolver=resolver, budget=b, redirects_followed=0)
    for bad in ("http://catalog.example/", "https://127.0.0.1/", "https://u@catalog.example/"):
        try:
            ep.verify_url(bad, allow, resolver)
        except ep.EgressPolicyError:
            pass
    fq.from_mapping({"name": "search_probe"})
    new = sorted(m.split(".")[0] for m in set(sys.modules) - before)
    banned = {"socket","ssl","http","urllib","urllib3","httpx","requests","aiohttp","asyncio","selectors","select","subprocess"}
    print(json.dumps({"events": events, "calls": calls, "network_modules_loaded": sorted(set(new) & banned)}))
    """
)


def test_running_the_whole_policy_creates_no_socket_event_and_loads_no_network_module() -> None:
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SCRIPT], capture_output=True, text=True, timeout=60, check=True, cwd=REPO
    )
    doc = json.loads(p.stdout.strip().splitlines()[-1])
    assert doc["events"] == [], doc["events"]
    assert doc["network_modules_loaded"] == [], doc["network_modules_loaded"]
    assert (
        len(doc["calls"]) == 2
    )  # one resolution for the request, one for the redirect hop; refused URLs: none
