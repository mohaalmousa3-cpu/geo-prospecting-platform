FROM node:22-slim AS build
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_BASEMAP_PROVIDER=none
ARG NEXT_PUBLIC_BASEMAP_TILE_URL=
ARG NEXT_PUBLIC_BASEMAP_ATTRIBUTION=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_BASEMAP_PROVIDER=${NEXT_PUBLIC_BASEMAP_PROVIDER} \
    NEXT_PUBLIC_BASEMAP_TILE_URL=${NEXT_PUBLIC_BASEMAP_TILE_URL} \
    NEXT_PUBLIC_BASEMAP_ATTRIBUTION=${NEXT_PUBLIC_BASEMAP_ATTRIBUTION}
WORKDIR /app
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi \
    && npm ci
COPY apps/frontend/ ./
RUN npm run build

FROM node:22-slim
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
