# One Dockerfile for the Python services; PACKAGE selects backend or worker (separate images, ADR-0011).
# Optional build secret `proxy_ca`: CA bundle for TLS-intercepting proxies (see infrastructure/README.md).
FROM python:3.12-slim AS base
ARG PACKAGE
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY packages/pycommon packages/pycommon
COPY apps/backend apps/backend
COPY workers/runner workers/runner
COPY workers/connectors workers/connectors
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi \
    && pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --package "${PACKAGE}" \
    && mkdir -p /data/processed && chown -R app:app /data /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
