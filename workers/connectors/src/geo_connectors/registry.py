"""Connector registry and `CONNECTOR_MODE` behaviour.

* `disabled` (default): no connector is returned; the caller gets `ConnectorsDisabled`.
* `fixture`: only the offline fixture connector is available.
* `live`: accepted as a configuration value but explicitly not available in Phase 3a (`LiveModeNotAvailable`).
"""

from __future__ import annotations

from collections.abc import Callable

from geo_connectors.contracts import Connector, ConnectorMode
from geo_connectors.errors import ConnectorsDisabled, LiveModeNotAvailable, UnknownConnector
from geo_connectors.fixture import FixtureConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Connector]] = {}

    def register(self, name: str, factory: Callable[[], Connector]) -> None:
        if name in self._factories:
            raise ValueError(f"connector {name!r} is already registered")
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def get(self, name: str) -> Connector:
        try:
            return self._factories[name]()
        except KeyError:
            raise UnknownConnector(f"unknown connector {name!r}") from None


def default_registry() -> ConnectorRegistry:
    reg = ConnectorRegistry()
    reg.register(FixtureConnector.name, FixtureConnector)
    return reg


def resolve_connector(
    mode: str | ConnectorMode, name: str, registry: ConnectorRegistry | None = None
) -> Connector:
    """Return the connector `name` for `mode`, or raise the explicit state for modes that offer none."""
    m = ConnectorMode(mode)  # ValueError on an unknown mode: never silently fall back
    if m is ConnectorMode.DISABLED:
        raise ConnectorsDisabled
    if m is ConnectorMode.LIVE:
        raise LiveModeNotAvailable
    return (registry or default_registry()).get(name)
