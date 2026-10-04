"""Connector errors. They carry explicit, user-facing reasons; nothing is swallowed or remapped."""

from __future__ import annotations


class ConnectorError(Exception):
    """Base class for connector failures."""


class ConnectorsDisabled(ConnectorError):  # noqa: N818 - state, not an error suffix
    """CONNECTOR_MODE=disabled: no connector may run."""

    def __init__(self) -> None:
        super().__init__("connectors disabled (CONNECTOR_MODE=disabled)")


class LiveModeNotAvailable(ConnectorError):  # noqa: N818
    """CONNECTOR_MODE=live is accepted as a value but is explicitly not available in Phase 3a."""

    def __init__(self) -> None:
        super().__init__("live connector mode is not available in Phase 3a (fixtures only)")


class UnknownConnector(ConnectorError):  # noqa: N818
    pass


class ConnectorRequestError(ConnectorError):
    """The request is outside the connector's contract or the ADR-0008 limits."""


class FixtureError(ConnectorError):
    """A fixture file is missing, malformed or not labelled synthetic."""
