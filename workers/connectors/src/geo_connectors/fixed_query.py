"""Strict, non-sensitive *fixed* verification queries (Phase 3b R8, offline definition only).

A fixed query is chosen **by name from a registry written in this file**. It carries no AOI, project, user
coordinate, user date, header, cookie, credential or endpoint path, and none can be supplied: a request
mapping may contain exactly one key, `name`, and every other key is refused with a code that says which
class of input it was.

Both entries are CANDIDATES for the owner-defined D8 verification slice. They are **not authorised to
execute** (`APPROVED_FOR_EXECUTION` is False and nothing in this repository can send them). They contain
only invented, project-independent constants (an arbitrary 0.01° box in open ocean and a past two-day
window), never a pilot area or a user value. They hold no host or port: a destination only exists after the
owner approves one (R4) and a caller injects it into `egress_policy`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from geo_connectors.egress_policy import EgressPolicyError, ensure_relative_path

APPROVED_FOR_EXECUTION = False
STATUS_LABEL = "CANDIDATE - not authorized to execute"

# name -> (method, path_and_query). Candidate collection per the owner's 2026-10-06 decision:
# sentinel-2-l2a only.
_DEFINITIONS: dict[str, tuple[str, str]] = {
    "collection_metadata": ("GET", "/v1/collections/sentinel-2-l2a"),
    "search_probe": (
        "GET",
        "/v1/search?collections=sentinel-2-l2a&limit=1&bbox=0,0,0.01,0.01"
        "&datetime=2024-01-01T00:00:00Z/2024-01-02T00:00:00Z",
    ),
}

# (code suffix, matching pattern) in priority order; keys are compared lower-case with `-`/spaces folded
# to `_`.
_FORBIDDEN_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "aoi_or_project",
        re.compile(r"aoi|project|geometr|polygon|intersect|coordinate|lat|lon|(?:^|_)points?(?:$|_)|geojson"),
    ),
    ("bbox", re.compile(r"bbox|bounds|extent")),
    ("endpoint", re.compile(r"path|url|uri|href|link|endpoint|route|base|host|port|scheme|query|method")),
    ("datetime", re.compile(r"date|time|start|end|interval|window|period")),
    ("cookie", re.compile(r"cookie|session")),
    ("header", re.compile(r"header|user_?agent|accept|referer|origin")),
    ("credential", re.compile(r"auth|token|password|passwd|secret|api_?key|credential|bearer|^key$|user")),
)


def _fail(code: str, message: str) -> EgressPolicyError:
    return EgressPolicyError(f"fixed_query_{code}", message)


@dataclass(frozen=True)
class FixedQuery:
    """A registry entry. Direct construction with anything that is not an exact registry entry is refused."""

    name: str
    method: str
    path_and_query: str

    def __post_init__(self) -> None:
        if _DEFINITIONS.get(self.name) != (self.method, self.path_and_query):
            raise _fail("not_registered", "a fixed query must equal an entry of the in-code registry")
        ensure_relative_path(self.path_and_query)  # a registry entry is itself a relative path, never a URL

    @property
    def label(self) -> str:
        return STATUS_LABEL


def fixed_query(name: object) -> FixedQuery:
    if not isinstance(name, str) or name not in _DEFINITIONS:
        raise _fail("unknown_name", "unknown fixed query name")
    method, path = _DEFINITIONS[name]
    return FixedQuery(name, method, path)


def fixed_query_names() -> tuple[str, ...]:
    return tuple(sorted(_DEFINITIONS))


def from_mapping(raw: object) -> FixedQuery:
    """Build a query from untrusted input. Exactly `{"name": <registered name>}` is accepted."""
    if not isinstance(raw, Mapping):
        raise _fail("not_a_mapping", "a fixed query request must be a mapping with a single `name` key")
    for key in raw:
        if not isinstance(key, str):
            raise _fail("unknown_field", "request keys must be strings")
        if key == "name":
            continue
        folded = re.sub(r"[-\s]+", "_", key.strip().lower())
        for code, pattern in _FORBIDDEN_CLASSES:
            if pattern.search(folded):
                raise _fail(code, f"field '{key[:40]}' is not accepted in a fixed query ({code})")
        raise _fail("unknown_field", f"field '{key[:40]}' is not accepted in a fixed query")
    if "name" not in raw:
        raise _fail("unknown_name", "a fixed query request needs a `name`")
    return fixed_query(raw["name"])
