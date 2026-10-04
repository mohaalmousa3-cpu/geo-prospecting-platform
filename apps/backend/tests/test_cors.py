"""CORS must match the API surface: every declared verb works from a browser, nothing else does."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.cors import ALLOWED_HEADERS, ELIGIBLE_METHODS, declared_methods, declared_operations

ORIGIN = "http://localhost:3000"
EVIL = "http://evil.example"
SAMPLE_UUID = "11111111-1111-1111-1111-111111111111"


def _noop() -> None:
    return None


def _noop2() -> None:
    return None


def route_methods(client: TestClient) -> list[tuple[str, str]]:
    out = []
    for path, method in declared_operations(client.app):  # type: ignore[arg-type]
        out.append((re.sub(r"\{[^}]+\}", SAMPLE_UUID, path), method))
    return out


def preflight(
    client: TestClient, path: str, method: str, origin: str = ORIGIN, headers: str = "content-type"
):  # type: ignore[no-untyped-def]
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_every_declared_route_method_passes_a_browser_preflight(client: TestClient) -> None:
    pairs = route_methods(client)
    assert len(pairs) >= 12  # sanity: the derivation really found the API surface (guards an empty list)
    for path, method in pairs:
        r = preflight(client, path, method)
        assert r.status_code == 200, (path, method, r.text)
        assert r.headers["access-control-allow-origin"] == ORIGIN
        assert method in r.headers["access-control-allow-methods"].split(", "), (path, method)


def test_allowed_methods_equal_the_union_of_route_methods(client: TestClient) -> None:
    declared = {m for _, m in route_methods(client)}
    assert set(declared_methods(client.app)) == declared  # type: ignore[arg-type]
    assert {"GET", "POST", "DELETE"} <= declared  # what the UI uses today


@pytest.mark.parametrize("method", ["TRACE", "CONNECT", "PROPFIND"])
def test_exotic_verbs_are_never_allowed(client: TestClient, method: str) -> None:
    assert preflight(client, "/api/v1/aois", method).status_code == 400
    assert method not in declared_methods(client.app)  # type: ignore[arg-type]


def test_a_verb_no_route_uses_is_not_allowed(client: TestClient) -> None:
    declared = {m for _, m in route_methods(client)}
    for method in sorted(ELIGIBLE_METHODS - declared):  # e.g. PUT/PATCH today; adapts when routes are added
        assert preflight(client, "/api/v1/aois", method).status_code == 400, method


def test_adding_a_route_extends_cors_automatically(engine) -> None:  # type: ignore[no-untyped-def]
    """Future-safety: a new PATCH route must not need a CORS edit."""
    from app.main import create_app
    from geo_common.config import Settings

    s = Settings(_env_file=None, CORS_ALLOWED_ORIGINS=ORIGIN)
    app = create_app(s, engine=engine)
    assert "PATCH" not in declared_methods(app)
    # the same derivation applied to an app that does have a PATCH route
    from fastapi import FastAPI

    other = FastAPI()
    other.add_api_route("/x", _noop, methods=["PATCH", "PUT"])
    assert declared_methods(other) == ["PATCH", "PUT"]
    router_app = FastAPI()  # lazily-included routers must be covered too (FastAPI >= 0.14x)
    from fastapi import APIRouter

    r = APIRouter()
    r.add_api_route("/y", _noop2, methods=["DELETE"])
    router_app.include_router(r, prefix="/api")
    assert declared_methods(router_app) == ["DELETE"]


def test_no_endpoint_is_hidden_from_the_openapi_document() -> None:
    """declared_methods() reads OpenAPI; a hidden endpoint would silently lose CORS."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    offenders = [str(p) for p in src.rglob("*.py") if "include_in_schema=False" in p.read_text()]
    assert offenders == []


def test_unlisted_origin_gets_no_cors_headers_for_any_declared_method(client: TestClient) -> None:
    for path, method in route_methods(client):
        r = preflight(client, path, method, origin=EVIL)
        assert "access-control-allow-origin" not in r.headers, (path, method)


def test_only_declared_headers_are_allowed_and_credentials_are_off(client: TestClient) -> None:
    assert preflight(client, "/api/v1/jobs", "POST", headers="authorization").status_code == 400
    assert preflight(client, "/api/v1/jobs", "POST", headers="x-custom").status_code == 400
    ok = preflight(client, "/api/v1/jobs", "POST", headers="content-type, x-request-id")
    assert ok.status_code == 200 and "access-control-allow-credentials" not in ok.headers
    assert set(h.lower() for h in ALLOWED_HEADERS) == {"content-type", "x-request-id"}


def test_preflight_is_cacheable_and_actual_responses_expose_the_request_id(client: TestClient) -> None:
    assert preflight(client, "/api/v1/jobs", "POST").headers["access-control-max-age"] == "600"
    r = client.get("/api/v1/health", headers={"Origin": ORIGIN})
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()
