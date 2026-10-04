from __future__ import annotations

import copy
from typing import Any

import pytest

from geo_common.envelope import IncompleteResultError, serialise_result, validate_result
from geo_common.models._generated import ResultEnvelope


def good() -> dict[str, Any]:
    return {
        "kind": "anomaly",
        "value": 0.4,
        "confidence": {"level": "low", "basis": "single synthetic test fixture"},
        "uncertainty": {"status": "not_quantified", "reason": "test fixture"},
        "explanation": {
            "summary": "Synthetic fixture for schema tests; not a scientific result.",
            "supporting": [],
            "counter_evidence": [],
            "limitations": ["synthetic"],
        },
        "sources": [{"dataset": "fixture", "version": "0", "acquired": "2000-01-01", "licence": "n/a"}],
        "provenance": {
            "run_id": "r1",
            "code_version": "test",
            "parameters": {},
            "created_at": "2026-01-01T00:00:00Z",
        },
        "disclaimer_id": "D-1",
        "validation_status": "unvalidated",
        "calibration_status": "uncalibrated",
        "engine_status": "experimental",
    }


def test_valid_result_serialises_and_matches_pydantic() -> None:
    out = serialise_result(good())
    ResultEnvelope.model_validate(out)


@pytest.mark.parametrize(
    "field",
    [
        "kind", "value", "confidence", "uncertainty", "explanation", "sources", "provenance",
        "disclaimer_id", "validation_status", "calibration_status", "engine_status",
    ],
)
def test_each_mandatory_field_is_required(field: str) -> None:
    bad = good()
    del bad[field]
    with pytest.raises(IncompleteResultError):
        serialise_result(bad)


def test_nothing_is_defaulted() -> None:
    bad = good()
    del bad["confidence"]
    with pytest.raises(IncompleteResultError):
        serialise_result(bad)
    assert "confidence" not in bad


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("validation_status",), "validated"),
        (("validation_status",), "confirmed"),
        (("kind",), "confirmed_gold"),
        (("kind",), "cave_detected"),
        (("confidence", "level"), "certain"),
        (("confidence", "basis"), ""),
        (("explanation", "limitations"), []),
        (("sources",), []),
        (("engine_status",), "production"),
        (("disclaimer_id",), "D-9"),
        (("uncertainty",), {"status": "quantified"}),
        (("uncertainty",), {"status": "not_quantified", "reason": ""}),
    ],
)
def test_invalid_values_rejected(path: tuple[str, ...], value: Any) -> None:
    bad = copy.deepcopy(good())
    node = bad
    for p in path[:-1]:
        node = node[p]
    node[path[-1]] = value
    assert validate_result(bad)


def test_unknown_fields_rejected() -> None:
    bad = good()
    bad["gold_found"] = True
    assert validate_result(bad)


def test_depth_gating() -> None:
    surface = good()
    surface["depth"] = {"value_m": 12, "uncertainty_m": 2, "method": "guess"}
    assert validate_result(surface)  # no basis
    surface["depth"]["basis"] = "satellite"
    assert validate_result(surface)  # basis not allowed
    ok = good()
    ok["disclaimer_id"] = "D-2"
    ok["depth"] = {"basis": "field_geophysics", "method": "ERT inversion", "value_m": 12, "uncertainty_m": 2}
    assert validate_result(ok) == []
    ok["disclaimer_id"] = "D-1"
    assert validate_result(ok)  # depth requires D-2


def test_deposit_model_requires_applicability() -> None:
    r = good()
    r["deposit_model"] = "orogenic"
    assert validate_result(r)
    r["applicability"] = "applicability_unknown"
    assert validate_result(r) == []
    r["deposit_model"] = "epithermal"
    assert validate_result(r)
