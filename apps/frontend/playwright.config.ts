import { defineConfig } from "@playwright/test";

/**
 * Browser smoke test (real Chromium → real Next.js → real FastAPI → real PostGIS).
 * It exists because two defects (MapLibre worker, CORS DELETE) passed every mocked-fetch unit test.
 *
 * Locally: needs PostgreSQL+PostGIS reachable with a database named by E2E_POSTGRES_DB, and either
 * Playwright's own browser (`npx playwright install chromium`) or E2E_CHROMIUM_PATH=/path/to/chrome.
 */
const env = process.env;
const API_PORT = 8000;
const WEB_PORT = 3000;
const apiBase = `http://127.0.0.1:${API_PORT}/api/v1`;

const db = {
  POSTGRES_USER: env.POSTGRES_USER ?? "geo",
  POSTGRES_PASSWORD: env.POSTGRES_PASSWORD ?? "geo",
  POSTGRES_HOST: env.POSTGRES_HOST ?? "localhost",
  POSTGRES_PORT: env.POSTGRES_PORT ?? "5432",
  POSTGRES_DB: env.E2E_POSTGRES_DB ?? "geo_e2e",
};

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0, // a flaky smoke test must be fixed, not retried into green
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: {
      executablePath: env.E2E_CHROMIUM_PATH || undefined,
      args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    },
  },
  webServer: [
    {
      // migrate then serve; the same code path as the Compose `migrate` + `backend` services
      command: `uv run python -m geo_common.migrate && uv run uvicorn app.main:app_factory --factory --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../..",
      url: `${apiBase}/health/ready`,
      timeout: 120_000,
      reuseExistingServer: !env.CI,
      env: { ...db, CORS_ALLOWED_ORIGINS: `http://127.0.0.1:${WEB_PORT}`, LOG_LEVEL: "WARNING" },
    },
    {
      command: `npm run build && npx next start -p ${WEB_PORT} -H 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      timeout: 300_000,
      reuseExistingServer: !env.CI,
      env: { NEXT_PUBLIC_API_BASE_URL: apiBase, NEXT_PUBLIC_BASEMAP_PROVIDER: "none" },
    },
  ],
});
