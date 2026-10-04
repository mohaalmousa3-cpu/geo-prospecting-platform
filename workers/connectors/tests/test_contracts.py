from __future__ import annotations

from datetime import date

import pytest
from helpers import ctx

from geo_connectors.contracts import (
    HARD_MAX_ITEMS,
    Connector,
    FetchContext,
    FetchResult,
    SourceMetadata,
    in_fetch_window,
)
from geo_connectors.errors import ConnectorRequestError


def _source() -> SourceMetadata:
    return SourceMetadata("t", "fixture", "d", "1", "2026-01-01T00:00:00Z", {"a": 1}, "0", True)


class Probe(Connector):
    name = "probe"

    def __init__(self, result: object = None, boom: bool = False) -> None:
        self.seen: list[bool] = []
        self.result = result
        self.boom = boom

    def _fetch(self, ctx: FetchContext) -> FetchResult:
        self.seen.append(in_fetch_window())
        if self.boom:
            raise RuntimeError("boom")
        return self.result if self.result is not None else FetchResult((), _source())  # type: ignore[return-value]


def test_fetch_window_is_set_only_during_fetch() -> None:
    p = Probe()
    assert in_fetch_window() is False
    p.fetch(ctx())
    assert p.seen == [True] and in_fetch_window() is False


def test_fetch_window_is_reset_when_fetch_raises() -> None:
    p = Probe(boom=True)
    with pytest.raises(RuntimeError):
        p.fetch(ctx())
    assert in_fetch_window() is False


def test_non_fetchresult_is_rejected() -> None:
    with pytest.raises(TypeError):
        Probe(result="nope").fetch(ctx())


@pytest.mark.parametrize(
    "kw",
    [
        {"aoi_geojson": {"type": "Point", "coordinates": [0, 0]}},
        {"start": date(2026, 5, 2), "end": date(2026, 5, 1)},
        {"start": date(2026, 1, 1), "end": date(2027, 1, 1)},  # 366 days > 365
        {"max_items": 0},
        {"max_items": HARD_MAX_ITEMS + 1},
        {"collections": ()},
    ],
)
def test_invalid_requests_are_rejected_before_fetch(kw: dict[str, object]) -> None:
    p = Probe()
    with pytest.raises(ConnectorRequestError):
        p.fetch(ctx(**kw))
    assert p.seen == []  # _fetch never ran


def test_window_limit_boundary_is_inclusive() -> None:
    Probe().fetch(ctx(start=date(2026, 1, 1), end=date(2026, 12, 31)))  # exactly 365 days


def test_too_many_records_from_a_connector_are_rejected() -> None:
    from geo_connectors.contracts import CatalogRecord

    recs = tuple(
        CatalogRecord(f"i{k}", "synthetic-optical", "2026-01-02T00:00:00Z", (0, 0, 1, 1)) for k in range(3)
    )
    with pytest.raises(ConnectorRequestError):
        Probe(result=FetchResult(recs, _source())).fetch(ctx(max_items=2))
