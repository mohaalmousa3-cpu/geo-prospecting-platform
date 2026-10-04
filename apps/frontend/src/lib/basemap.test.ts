import { describe, expect, it } from "vitest";

import { resolveBasemap } from "./basemap";

describe("resolveBasemap", () => {
  it("defaults to OpenStreetMap, flagged development-only, with attribution", () => {
    for (const env of [{}, { provider: "" }, { provider: " OSM " }]) {
      const b = resolveBasemap(env);
      expect(b).toMatchObject({
        provider: "osm",
        devOnly: true,
        attribution: "© OpenStreetMap contributors",
      });
      expect(b.tiles).toBe("https://tile.openstreetmap.org/{z}/{x}/{y}.png");
    }
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
