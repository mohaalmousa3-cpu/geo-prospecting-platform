"""CORS policy derived from the operations the API actually declares.

A hand-written method list drifts: it silently broke browser `DELETE` calls once (the preflight was
refused while curl and mocked-fetch tests worked). Deriving the list from the declared operations means
every verb an endpoint uses is allowed in the browser, and no verb without an endpoint ever is.

The source is the app's OpenAPI document, not `app.routes`: FastAPI includes routers lazily, so
`app.routes` is not a flat list of routes. Consequence: an endpoint declared with
hidden from the schema (include_in_schema disabled) would not be covered, so the API must not hide endpoints from its schema
(a test enforces that the schema lists every operation the tests reach).
"""

from __future__ import annotations

from fastapi import FastAPI

# The only verbs ever eligible. OPTIONS is handled by the middleware itself; TRACE/CONNECT never.
ELIGIBLE_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})
ALLOWED_HEADERS = ["Content-Type", "X-Request-ID"]  # no Authorization: V1 has no authentication
EXPOSED_HEADERS = ["X-Request-ID"]
PREFLIGHT_MAX_AGE_SECONDS = 600


def declared_operations(app: FastAPI) -> list[tuple[str, str]]:
    """(path template, METHOD) for every operation in the OpenAPI document, eligible methods only."""
    paths: dict[str, dict[str, object]] = app.openapi().get("paths", {})
    return sorted(
        (path, method.upper())
        for path, ops in paths.items()
        for method in ops
        if method.upper() in ELIGIBLE_METHODS
    )


def declared_methods(app: FastAPI) -> list[str]:
    return sorted({m for _, m in declared_operations(app)})
