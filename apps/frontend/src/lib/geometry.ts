import type { Bbox, LonLat } from "@/types/contracts";

/** Normalise two map corners into west/south/east/north. */
export function rectangleFromCorners(a: LonLat, b: LonLat) {
  return {
    west: Math.min(a[0], b[0]),
    south: Math.min(a[1], b[1]),
    east: Math.max(a[0], b[0]),
    north: Math.max(a[1], b[1]),
  };
}

/** Parse a user-typed decimal ("12.5", "-3,25" with comma). Returns null if not a finite number. */
export function parseNumber(text: string): number | null {
  const t = text.trim().replace(",", ".");
  if (t === "" || !/^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(t)) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

/** Wrap map longitudes (maplibre can report lng outside -180..180 after panning). */
export function wrapLon(lon: number): number {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

export function formatArea(km2: number): string {
  if (km2 >= 10) return `${km2.toFixed(1)} km²`;
  if (km2 >= 1) return `${km2.toFixed(2)} km²`;
  return `${km2.toFixed(3)} km²`;
}

export function formatCoord(n: number): string {
  return n.toFixed(5);
}

export function bboxCenter(b: Bbox): LonLat {
  return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
}

/** Polygon in-progress drawing: remove consecutive duplicates (double-click adds the same point twice). */
export function dedupeConsecutive(points: LonLat[]): LonLat[] {
  return points.filter((p, i) => i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1]);
}
