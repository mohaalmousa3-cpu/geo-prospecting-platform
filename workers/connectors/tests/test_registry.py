from __future__ import annotations

import pytest

from geo_common.config import Settings
from geo_connectors.contracts import ConnectorMode
from geo_connectors.errors import ConnectorsDisabled, LiveModeNotAvailable, UnknownConnector
from geo_connectors.fixture import FixtureConnector
from geo_connectors.registry import ConnectorRegistry, default_registry, resolve_connector


def test_default_mode_is_disabled() -> None:
    assert Settings(_env_file=None).CONNECTOR_MODE == "disabled"


def test_disabled_returns_no_connector_and_says_so() -> None:
    with pytest.raises(ConnectorsDisabled, match="connectors disabled"):
        resolve_connector("disabled", "fixture")


def test_live_is_explicitly_not_available() -> None:
    with pytest.raises(LiveModeNotAvailable, match="not available"):
        resolve_connector(ConnectorMode.LIVE, "fixture")


def test_fixture_mode_returns_the_fixture_connector() -> None:
    assert isinstance(resolve_connector("fixture", "fixture"), FixtureConnector)


def test_unknown_connector_and_unknown_mode_are_errors_not_fallbacks() -> None:
    with pytest.raises(UnknownConnector):
        resolve_connector("fixture", "nope")
    with pytest.raises(ValueError):
        resolve_connector("lve", "fixture")


def test_duplicate_registration_is_rejected() -> None:
    reg = default_registry()
    assert reg.names() == ["fixture"]
    with pytest.raises(ValueError):
        reg.register("fixture", FixtureConnector)


def test_settings_accept_only_known_modes() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, CONNECTOR_MODE="stac")  # type: ignore[arg-type]
    assert isinstance(ConnectorRegistry().names(), list)
