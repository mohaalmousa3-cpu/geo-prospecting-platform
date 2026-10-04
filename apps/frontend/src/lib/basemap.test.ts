import { describe, expect, it } from "vitest";

import { resolveBasemap } from "./basemap";

describe("resolveBasemap", () => {
  it("defaults to no basemap, silently, when nothing is configured", () => {
    for (const env of [
      {},
      { provider: "" },
      { provider: "  " },
      { nodeEnv: "development" },
      { nodeEnv: "production" },
    ]) {
      const b = resolveBasemap(env);
      expect(b).toMatchObject({ provider: "none", tiles: null, devOnly: false });
      expect(b.warning).toBeUndefined();
    }
  });

  it("osm is opt-in and works outside production builds, flagged development-only", () => {
    for (const nodeEnv of ["development", "test", undefined]) {
      const b = resolveBasemap({ provider: " OSM ", nodeEnv });
      expect(b).toMatchObject({
        provider: "osm",
        devOnly: true,
        attribution: "© OpenStreetMap contributors",
      });
      expect(b.tiles).toBe("https://tile.openstreetmap.org/{z}/{x}/{y}.png");
      expect(b.warning).toBeUndefined();
    }
  });

  it("osm is refused in production builds with a visible warning", () => {
    const b = resolveBasemap({ provider: "osm", nodeEnv: "production" });
    expect(b).toMatchObject({ provider: "none", tiles: null });
    expect(b.warning).toMatch(/local development only/);
    expect(b.warning).toMatch(/xyz/);
  });

  it("a tile URL without an explicit provider is ignored (no implicit xyz)", () => {
    const b = resolveBasemap({
      tileUrl: "https://tiles.example/{z}/{x}/{y}.png",
      attribution: "© Example",
    });
    expect(b).toMatchObject({ provider: "none", tiles: null });
  });

  it("none makes no tile requests", () => {
    expect(
      resolveBasemap({ provider: "none", tileUrl: "https://x/{z}/{x}/{y}.png" }),
    ).toMatchObject({
      provider: "none",
      tiles: null,
    });
  });

  it("accepts a custom https XYZ server when attribution is given", () => {
    const b = resolveBasemap({
      provider: "xyz",
      tileUrl: "https://tiles.example/{z}/{x}/{y}.png",
      attribution: "© Example",
    });
    expect(b).toMatchObject({
      provider: "xyz",
      tiles: "https://tiles.example/{z}/{x}/{y}.png",
      devOnly: false,
    });
    expect(b.warning).toBeUndefined();
  });

  it("allows plain http only for localhost", () => {
    const ok = resolveBasemap({
      provider: "xyz",
      tileUrl: "http://localhost:8080/{z}/{x}/{y}.png",
      attribution: "a",
    });
    expect(ok.provider).toBe("xyz");
    const bad = resolveBasemap({
      provider: "xyz",
      tileUrl: "http://tiles.example/{z}/{x}/{y}.png",
      attribution: "a",
    });
    expect(bad).toMatchObject({ provider: "none", tiles: null });
    expect(bad.warning).toMatch(/https/);
  });

  it.each([
    [{ provider: "xyz" }, /TILE_URL/],
    [
      { provider: "xyz", tileUrl: "https://t.example/tiles.png", attribution: "a" },
      /\{z\}, \{x\} and \{y\}/,
    ],
    [{ provider: "xyz", tileUrl: "https://t.example/{z}/{x}/{y}.png" }, /attribution/i],
    [{ provider: "mapbox" }, /Unknown basemap provider "mapbox"/],
  ])("falls back to no basemap with a warning for %j", (env, msg) => {
    const b = resolveBasemap(env);
    expect(b).toMatchObject({ provider: "none", tiles: null });
    expect(b.warning).toMatch(msg);
  });
});
