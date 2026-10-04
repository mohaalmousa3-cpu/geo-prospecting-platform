/**
 * Basemap provider abstraction (ADR-0013). The map never hard-codes a tile server: it asks
 * `resolveBasemap` which provider is configured. Adding a provider = one new case here.
 *
 * Privacy: tile requests reveal the viewed map area (not the AOI geometry) to the provider.
 * "none" makes no third-party requests.
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
  const provider = (env.provider ?? "").trim().toLowerCase() || "osm";
  if (provider === "none") return NONE;
  if (provider === "osm") {
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
    provider: process.env.NEXT_PUBLIC_BASEMAP_PROVIDER,
    tileUrl: process.env.NEXT_PUBLIC_BASEMAP_TILE_URL,
    attribution: process.env.NEXT_PUBLIC_BASEMAP_ATTRIBUTION,
  });
}
