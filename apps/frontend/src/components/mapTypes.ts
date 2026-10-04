import type { Bbox, GeoJsonPolygon, LonLat } from "@/types/contracts";

export type DrawMode = "none" | "center" | "rectangle" | "polygon";

export interface MapViewProps {
  mode: DrawMode;
  /** Validated (not yet saved) AOI. */
  draft: GeoJsonPolygon | null;
  /** AOI selected from the saved list. */
  saved: GeoJsonPolygon | null;
  /** Fit the view to this bbox when it changes. */
  fitTo: Bbox | null;
  /** Centre marker for point+radius sketches. */
  marker: LonLat | null;
  /** In-progress polygon vertices (controlled by the parent). */
  polygonPoints: LonLat[];
  onCenter: (p: LonLat) => void;
  onRectangle: (a: LonLat, b: LonLat) => void;
  onPolygonPoint: (p: LonLat) => void;
  onPolygonFinish: () => void;
  onCancel: () => void;
}
