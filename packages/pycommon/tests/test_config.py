from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from geo_common.config import Settings

ROOT = Path(__file__).resolve().parents[3]
# Read by Docker Compose only, or by Next.js; mirrored in Settings where noted.
NOT_IN_SETTINGS: set[str] = set()


def env_example_keys() -> set[str]:
    keys = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        m = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if m:
            keys.add(m.group(1))
    return keys


def test_env_example_matches_settings_fields() -> None:
    assert env_example_keys() - NOT_IN_SETTINGS == set(Settings.model_fields)


def test_defaults_match_adr_0008() -> None:
    s = Settings(_env_file=None)
    assert (s.MAX_AOI_AREA_KM2, s.MAX_RADIUS_KM, s.MIN_AOI_AREA_KM2) == (25, 2.5, 0.01)
    assert (s.MAX_SCENES_PER_JOB, s.JOB_TIMEOUT_SECONDS, s.MAX_QUEUED_JOBS) == (20, 1800, 10)
    assert s.MAX_UPLOAD_MB == 10 and s.MAX_ARCHIVE_UNCOMPRESSED_MB == 50
    assert s.ENABLE_EARTH_ENGINE is False and s.ENABLE_INSAR_WORKER is False
    assert s.BIND_HOST == "127.0.0.1"


def test_env_example_values_equal_code_defaults() -> None:
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text().splitlines()
        if re.match(r"^[A-Z][A-Z0-9_]*=", line)
    )
    s = Settings(_env_file=None)
    for key in ("MAX_AOI_AREA_KM2", "MAX_RADIUS_KM", "MAX_SCENES_PER_JOB", "JOB_TIMEOUT_SECONDS"):
        assert float(values[key]) == float(getattr(s, key))


@pytest.mark.parametrize(
    "env",
    [
        {"MAX_AOI_AREA_KM2": "-1"},
        {"MAX_QUEUED_JOBS": "0"},
        {"JOB_TIMEOUT_SECONDS": "0"},
        {"MIN_AOI_AREA_KM2": "30"},
        {"JOB_LEASE_SECONDS": "5000"},
        {"STORAGE_BACKEND": "s3"},
        {"LOG_LEVEL": "LOUD"},
    ],
)
def test_invalid_values_rejected(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_override_and_cors_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_AOI_AREA_KM2", "10")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://a.test, http://b.test")
    s = Settings(_env_file=None)
    assert s.MAX_AOI_AREA_KM2 == 10
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_no_forbidden_infra_settings() -> None:
    names = " ".join(Settings.model_fields).upper()
    for bad in ("REDIS", "S3_", "MINIO", "JWT", "AUTH", "OAUTH"):
        assert bad not in names


def test_database_url_quotes_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")
    assert "p%40ss%2Fword" in Settings(_env_file=None).database_url
