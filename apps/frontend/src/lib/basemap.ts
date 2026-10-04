/**
 * Basemap provider abstraction (ADR-0013; default changed to "none" in the Phase 2.5 follow-ups).
 * The map never hard-codes a tile server: it asks `resolveBasemap` which provider is configured.
 *
 * - Default (unset/empty) is "none": no third-party requests.
 * - "osm" is opt-in and honoured only outside production builds (local `next dev` / tests).
 * - "xyz" needs an explicit provider choice, an https URL ({z}/{x}/{y}) and an attribution.
 * - Any invalid configuration falls back to "none" with a visible warning.
 *
 * Privacy: tile requests reveal the viewed map area (not the AOI geometry) to the provider.
 */
export type BasemapProviderId = "osm" | "xyz" | "none";

export interface Basemap {
  provider: BasemapProviderId;
  /** Raster XYZ template, or null for no basemap. */
  tiles: string | null;
  attribution: string;
  maxzoom: number;
  /** Human-readable name shown in the UI. */
  label: string;
  /** True when the provider's terms only allow low-volume development use. */
  devOnly: boolean;
  /** Set when the configuration was invalid and we fell back to "none". */
  warning?: string;
}

export interface BasemapEnv {
  provider?: string;
  tileUrl?: string;
  attribution?: string;
  /** NODE_ENV of the build. "production" disables the development-only osm provider. */
  nodeEnv?: string;
}

const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const NONE: Basemap = {
  provider: "none",
  tiles: null,
  attribution: "",
  maxzoom: 19,
  label: "No basemap",
  devOnly: false,
};

const isLocalHttp = (u: string) => /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(u);

export function resolveBasemap(env: BasemapEnv): Basemap {
  const provider = (env.provider ?? "").trim().toLowerCase() || "none";
  if (provider === "none") return NONE;
  if (provider === "osm") {
    if (env.nodeEnv === "production")
      return {
        ...NONE,
        warning:
          "OpenStreetMap tiles are opt-in for local development only (next dev) and are disabled in production builds; " +
          "showing no basemap. Use provider xyz with a tile server you are licensed to use.",
      };
    return {
      provider: "osm",
      tiles: OSM_TILES,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
      label: "OpenStreetMap (development use only)",
      devOnly: true,
    };
  }
  if (provider === "xyz") {
    const url = (env.tileUrl ?? "").trim();
    const attribution = (env.attribution ?? "").trim();
    const fail = (warning: string): Basemap => ({ ...NONE, warning });
    if (!url)
      return fail("Basemap provider xyz needs NEXT_PUBLIC_BASEMAP_TILE_URL; showing no basemap.");
    if (!/\{z\}/.test(url) || !/\{x\}/.test(url) || !/\{y\}/.test(url))
      return fail("Tile URL must contain {z}, {x} and {y}; showing no basemap.");
    if (!url.startsWith("https://") && !isLocalHttp(url))
      return fail(
        "Tile URL must use https (http is allowed only for localhost); showing no basemap.",
      );
    if (!attribution)
      return fail(
        "Basemap attribution is required (NEXT_PUBLIC_BASEMAP_ATTRIBUTION); showing no basemap.",
      );
    return {
      provider: "xyz",
      tiles: url,
      attribution,
      maxzoom: 19,
      label: "Custom tile server",
      devOnly: false,
    };
  }
  return { ...NONE, warning: `Unknown basemap provider "${provider}"; showing no basemap.` };
}

/** Reads the build-time env (Next inlines literal `process.env.NEXT_PUBLIC_*` accesses). */
export function basemapFromEnv(): Basemap {
  return resolveBasemap({
    nodeEnv: process.env.NODE_ENV,
    provider: process.env.NEXT_PUBLIC_BASEMAP_PROVIDER,
    tileUrl: process.env.NEXT_PUBLIC_BASEMAP_TILE_URL,
    attribution: process.env.NEXT_PUBLIC_BASEMAP_ATTRIBUTION,
  });
}
