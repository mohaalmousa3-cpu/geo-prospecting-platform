from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api import aois, health, jobs, projects
from app.cors import ALLOWED_HEADERS, EXPOSED_HEADERS, PREFLIGHT_MAX_AGE_SECONDS, declared_methods
from app.errors import install_error_handlers
from app.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from geo_common.config import Settings, get_settings
from geo_common.db import make_engine
from geo_common.logging_setup import configure_logging
from geo_common.queue import JobQueue
from geo_common.queue_pg import PostgresJobQueue

API_PREFIX = "/api/v1"

DESCRIPTION = """
**V1 has no authentication. Local/private use only — do not expose to the public internet.**

Outputs of this platform are prospectivity/anomaly layers, never confirmation of gold, caves or voids.
Phase 2.5 exposes health checks, a `noop` job, projects and AOI input/validation/persistence.
No analysis, scoring, remote-sensing, Earth Engine or scientific result exists yet.
"""


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    queue: JobQueue | None = None,
) -> FastAPI:
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not app.state.engine_injected:
            app.state.engine = make_engine(s.database_url)
            app.state.queue = PostgresJobQueue(
                app.state.engine,
                max_queued_jobs=s.MAX_QUEUED_JOBS,
                default_max_attempts=s.JOB_MAX_ATTEMPTS,
            )
        yield
        if not app.state.engine_injected:
            app.state.engine.dispose()

    configure_logging(s.LOG_LEVEL)
    app = FastAPI(
        title="geo-prospecting-platform API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.engine_injected = engine is not None
    if engine is not None:
        app.state.engine = engine
        app.state.queue = queue or PostgresJobQueue(
            engine, max_queued_jobs=s.MAX_QUEUED_JOBS, default_max_attempts=s.JOB_MAX_ATTEMPTS
        )
    app.state.settings = s

    install_error_handlers(app)
    # Routers first: the CORS method list is derived from the routes that actually exist.
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(jobs.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    app.include_router(aois.router, prefix=API_PREFIX)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=declared_methods(app),
        allow_headers=ALLOWED_HEADERS,
        expose_headers=EXPOSED_HEADERS,
        allow_credentials=False,
        max_age=PREFLIGHT_MAX_AGE_SECONDS,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=s.max_request_bytes)
    app.add_middleware(RequestIdMiddleware)
    return app


def app_factory() -> FastAPI:
    return create_app()
