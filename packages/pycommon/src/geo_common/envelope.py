"""Envelope-enforcing serialiser (ADR-0009).

Refuses to serialise a result missing any mandatory field. It never fills in defaults:
a flattering default for confidence/uncertainty/validation is a scientific defect.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_SCHEMA_PATH = Path(__file__).parent / "models" / "geo-contracts.schema.json"


class IncompleteResultError(ValueError):
    """The result does not satisfy the mandatory result envelope."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("incomplete result refused: " + "; ".join(problems))
        self.problems = problems


@lru_cache
def _validator() -> Draft7Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    sub = {"$ref": "#/definitions/ResultEnvelope", "definitions": schema["definitions"]}
    return Draft7Validator(sub)


def validate_result(candidate: Mapping[str, Any]) -> list[str]:
    errors = sorted(_validator().iter_errors(dict(candidate)), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


def serialise_result(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of a valid result; raise IncompleteResultError otherwise."""
    problems = validate_result(candidate)
    if problems:
        raise IncompleteResultError(problems)
    return json.loads(json.dumps(dict(candidate), default=str))
