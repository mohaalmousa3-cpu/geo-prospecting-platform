"""Connector contract: a *pure* function from a `FetchContext` to a `FetchResult`.

`fetch()` receives everything through `FetchContext` and returns records plus source metadata. It must not
do database or storage I/O and must not open network connections; the handler (a later checkpoint) does I/O
outside the fetch window. The window is tracked with a `contextvars` flag, so test infrastructure can block
network access only while a connector runs, without this package importing `socket` (plan T5/T8).

Records are catalogue metadata. They carry no confidence, score or interpretation and are not scientific
results.
"""

from __future__ import annotations

import contextvars
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, ClassVar

from geo_connectors.errors import ConnectorRequestError

HARD_MAX_ITEMS = 100  # absolute ceiling above any configured MAX_SCENES_PER_JOB (ADR-0008 values are lower)
_FETCH_WINDOW: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "geo_connectors_fetch_window", default=False
)


def in_fetch_window() -> bool:
    """True while a connector's `fetch()` is executing in the current context."""
    return _FETCH_WINDOW.get()


class ConnectorMode(StrEnum):
    DISABLED = "disabled"
    FIXTURE = "fixture"
    LIVE = "live"


@dataclass(frozen=True)
class FetchContext:
    """Inputs of one catalogue search. Limits come from settings (ADR-0008) and are re-checked here."""

    aoi_geojson: Mapping[str, Any]  # a validated EPSG:4326 Polygon (AOI validation happens upstream)
    start: date
    end: date
    collections: tuple[str, ...]
    max_items: int
    max_window_days: int
    fixture_name: str = "synthetic_catalog_v1"  # fixture connector only; ignored by others

    def validate(self) -> None:
        if self.aoi_geojson.get("type") != "Polygon":
            raise ConnectorRequestError("aoi_geojson must be a GeoJSON Polygon")
        if self.end < self.start:
            raise ConnectorRequestError("end must not precede start")
        window = (self.end - self.start).days + 1
        if window > self.max_window_days:
            raise ConnectorRequestError(
                f"time window of {window} days exceeds the limit of {self.max_window_days}"
            )
        if not 1 <= self.max_items <= HARD_MAX_ITEMS:
            raise ConnectorRequestError(f"max_items must be within 1..{HARD_MAX_ITEMS}")
        if not self.collections:
            raise ConnectorRequestError("at least one collection is required")


@dataclass(frozen=True)
class CatalogRecord:
    """One catalogue entry (metadata only)."""

    item_id: str
    collection: str
    acquired: str  # ISO 8601 date-time, UTC
    bbox: tuple[float, float, float, float]  # west, south, east, north (EPSG:4326)
    properties: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceMetadata:
    """Where the records came from (CLAUDE.md §4.6): dataset, version, date, parameters, code version."""

    connector: str
    kind: str  # "fixture" in Phase 3a
    dataset: str
    dataset_version: str
    retrieved_at: str  # for fixtures: the fixture's own declared generation date (deterministic)
    parameters: Mapping[str, Any]
    code_version: str
    synthetic: bool


@dataclass(frozen=True)
class FetchResult:
    records: tuple[CatalogRecord, ...]
    source: SourceMetadata
    truncated: bool = False  # True if more records matched than max_items


class Connector(ABC):
    """Base class. Subclasses implement `_fetch`; callers use `fetch`."""

    name: ClassVar[str]

    def fetch(self, ctx: FetchContext) -> FetchResult:
        ctx.validate()
        token = _FETCH_WINDOW.set(True)
        try:
            result = self._fetch(ctx)
        finally:
            _FETCH_WINDOW.reset(token)
        if not isinstance(result, FetchResult):
            raise TypeError(f"{type(self).__name__}._fetch must return FetchResult")
        if len(result.records) > ctx.max_items:
            raise ConnectorRequestError("connector returned more records than max_items")
        return result

    @abstractmethod
    def _fetch(self, ctx: FetchContext) -> FetchResult: ...
