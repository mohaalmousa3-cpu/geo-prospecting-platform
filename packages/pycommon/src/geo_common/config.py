"""Shared typed configuration. Every variable is documented in `.env.example`.

Limits are provisional operational safeguards, not validated scientific thresholds (ADR-0008).
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import PositiveFloat, PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

_REQUEST_SLACK_BYTES = 1_048_576  # headroom for multipart overhead


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    # General
    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    BIND_HOST: str = "127.0.0.1"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Database
    POSTGRES_USER: str = "geo"
    POSTGRES_PASSWORD: str = "change-me"  # noqa: S105 - dev placeholder
    POSTGRES_DB: str = "geo_prospecting"
    POSTGRES_HOST: str = "postgis"
    POSTGRES_PORT: PositiveInt = 5432

    # Storage (local only, ADR-0006)
    STORAGE_BACKEND: Literal["local"] = "local"
    STORAGE_LOCAL_PATH: str = "./data/processed"

    # Job queue (PostgreSQL-backed, ADR-0007)
    WORKER_CONCURRENCY: PositiveInt = 1
    WORKER_POLL_INTERVAL_SECONDS: PositiveFloat = 2.0
    JOB_LEASE_SECONDS: PositiveInt = 60
    JOB_MAX_ATTEMPTS: PositiveInt = 2
    MAX_QUEUED_JOBS: PositiveInt = 10

    # Provisional operational limits (ADR-0008)
    MAX_AOI_AREA_KM2: PositiveFloat = 25
    MAX_RADIUS_KM: PositiveFloat = 2.5
    MIN_AOI_AREA_KM2: PositiveFloat = 0.01
    MAX_AOI_VERTICES: PositiveInt = 2000
    MAX_UPLOAD_MB: PositiveInt = 10
    MAX_PROJECTS: PositiveInt = 20
    MAX_STORED_AOIS: PositiveInt = 100
    MAX_ARCHIVE_UNCOMPRESSED_MB: PositiveInt = 50
    MAX_ARCHIVE_FILES: PositiveInt = 50
    MAX_TIME_WINDOW_DAYS: PositiveInt = 365
    MAX_SCENES_PER_JOB: PositiveInt = 20
    JOB_TIMEOUT_SECONDS: PositiveInt = 1800

    # Frontend-facing (read by Next.js; mirrored here only so config stays in one list)
    NEXT_PUBLIC_API_BASE_URL: str = "http://localhost:8000/api/v1"
    NEXT_PUBLIC_CESIUM_ION_TOKEN: str = ""
    NEXT_PUBLIC_BASEMAP_PROVIDER: Literal["osm", "xyz", "none"] = "none"
    NEXT_PUBLIC_BASEMAP_TILE_URL: str = ""
    NEXT_PUBLIC_BASEMAP_ATTRIBUTION: str = ""

    # Data connectors (ADR-0014): `disabled` opens no connector and no network; `fixture` serves committed
    # synthetic fixtures offline; `live` is accepted but explicitly NOT AVAILABLE in Phase 3a.
    CONNECTOR_MODE: Literal["disabled", "fixture", "live"] = "disabled"

    # Optional connectors / workers: disabled by default (ADR-0004)
    ENABLE_EARTH_ENGINE: bool = False
    ENABLE_INSAR_WORKER: bool = False
    ENABLE_GEMPY_WORKER: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> Settings:
        if self.MIN_AOI_AREA_KM2 >= self.MAX_AOI_AREA_KM2:
            raise ValueError("MIN_AOI_AREA_KM2 must be smaller than MAX_AOI_AREA_KM2")
        if self.JOB_LEASE_SECONDS >= self.JOB_TIMEOUT_SECONDS:
            raise ValueError("JOB_LEASE_SECONDS must be smaller than JOB_TIMEOUT_SECONDS")
        circle = math.pi * self.MAX_RADIUS_KM**2
        if circle > self.MAX_AOI_AREA_KM2:
            log.warning(
                "MAX_RADIUS_KM circle (%.2f km2) exceeds MAX_AOI_AREA_KM2 (%.2f km2)",
                circle,
                self.MAX_AOI_AREA_KM2,
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+pg8000://{quote(self.POSTGRES_USER, safe='')}"
            f":{quote(self.POSTGRES_PASSWORD, safe='')}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def max_request_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024 + _REQUEST_SLACK_BYTES


@lru_cache
def get_settings() -> Settings:
    return Settings()
