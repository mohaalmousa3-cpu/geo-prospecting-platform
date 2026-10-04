/* Generated from packages/schemas. DO NOT EDIT. */

/**
 * Phase 1 allows only the noop job. Later phases extend this enum.
 */
export type JobType = "noop";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled" | "insufficient_data";
export type Uncertainty = QuantifiedUncertainty | NotQuantifiedUncertainty;
export type AoiName = string;
export type AoiMethod = "point_radius" | "rectangle" | "polygon" | "geojson" | "kml" | "kmz" | "shapefile";
/**
 * [longitude, latitude] in EPSG:4326
 *
 * @minItems 2
 * @maxItems 2
 */
export type LonLat = [number, number];
/**
 * [west, south, east, north]
 *
 * @minItems 4
 * @maxItems 4
 */
export type Bbox = [number, number, number, number];

/**
 * Shared contracts (ADR-0009, ADR-0010, ADR-0011). Single source of truth; Pydantic and TypeScript types are generated from this file.
 */
export interface GeoContracts {
  job?: Job;
  result_envelope?: ResultEnvelope;
  aoi?: Aoi;
  aoi_draft?: AoiDraft;
  aoi_list?: AoiList;
  aoi_limits?: AoiLimits;
  aoi_point_radius_request?: AoiPointRadiusRequest;
  aoi_rectangle_request?: AoiRectangleRequest;
  aoi_polygon_request?: AoiPolygonRequest;
}
export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  priority: number;
  attempts: number;
  max_attempts: number;
  cancel_requested: boolean;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}
/**
 * Mandatory envelope for every layer/target. No `confirmed_*` kinds exist; validation_status is unvalidated only in V1 (ADR-0010).
 */
export interface ResultEnvelope {
  kind: "prospectivity" | "anomaly" | "evidence" | "geophysics_model";
  value: number | string | null;
  confidence: Confidence;
  uncertainty: Uncertainty;
  explanation: Explanation;
  /**
   * @minItems 1
   */
  sources: [Source, ...Source[]];
  provenance: Provenance;
  disclaimer_id: "D-1" | "D-2";
  validation_status: "unvalidated";
  calibration_status: "uncalibrated" | "calibrated";
  engine_status: "experimental" | "validated";
  deposit_model?: "orogenic";
  applicability?: "applicable" | "applicability_unknown";
  depth?: Depth;
}
export interface Confidence {
  level: "low" | "moderate" | "high";
  /**
   * Why this level: data quality, concordant evidence lines, validation status, coverage.
   */
  basis: string;
}
export interface QuantifiedUncertainty {
  status: "quantified";
  method: string;
  value: number;
  unit?: string;
}
export interface NotQuantifiedUncertainty {
  status: "not_quantified";
  reason: string;
}
export interface Explanation {
  summary: string;
  supporting: string[];
  counter_evidence: string[];
  /**
   * @minItems 1
   */
  limitations: [string, ...string[]];
}
export interface Source {
  dataset: string;
  version: string;
  /**
   * Acquisition date or interval (ISO 8601).
   */
  acquired: string;
  licence: string;
  url?: string;
  via?: "stac" | "earth_engine" | "direct" | "user_upload";
}
export interface Provenance {
  run_id: string;
  code_version: string;
  parameters: {};
  created_at: string;
  aoi_hash?: string;
  crs?: string;
  dependency_versions?: {
    [k: string]: string;
  };
}
/**
 * Present only with a geophysics/verification basis (docs/scientific-constraints.md rule 4). Surface-only data MUST NOT produce depth.
 */
export interface Depth {
  basis: "field_geophysics" | "direct_verification";
  method: string;
  value_m: number;
  uncertainty_m: number;
}
export interface Aoi {
  id: string;
  name: AoiName;
  method: AoiMethod;
  geometry: GeoJsonPolygon;
  bbox: Bbox;
  area_km2: number;
  vertex_count: number;
  working_crs: string;
  details: {};
  warnings: string[];
  created_at: string;
}
export interface GeoJsonPolygon {
  type: "Polygon";
  coordinates: LonLat[][];
}
/**
 * Validated, normalised AOI that has not been persisted. Geometry and bookkeeping only; no analysis.
 */
export interface AoiDraft {
  method: AoiMethod;
  geometry: GeoJsonPolygon;
  bbox: Bbox;
  area_km2: number;
  vertex_count: number;
  working_crs: string;
  details: {};
  warnings: string[];
}
export interface AoiList {
  items: AoiSummary[];
  total: number;
}
export interface AoiSummary {
  id: string;
  name: AoiName;
  method: AoiMethod;
  bbox: Bbox;
  area_km2: number;
  created_at: string;
}
/**
 * Provisional operational safeguards (ADR-0008), not scientific thresholds.
 */
export interface AoiLimits {
  max_area_km2: number;
  min_area_km2: number;
  max_radius_m: number;
  max_vertices: number;
  max_upload_mb: number;
  max_stored_aois: number;
  max_abs_latitude: number;
  supported_upload_formats: string[];
}
export interface AoiPointRadiusRequest {
  method: "point_radius";
  name?: AoiName;
  lat: number;
  lon: number;
  radius_m: number;
}
export interface AoiRectangleRequest {
  method: "rectangle";
  name?: AoiName;
  west: number;
  south: number;
  east: number;
  north: number;
}
export interface AoiPolygonRequest {
  method: "polygon";
  name?: AoiName;
  /**
   * Outer ring only; open rings are closed automatically.
   *
   * @minItems 3
   */
  coordinates: [LonLat, LonLat, LonLat, ...LonLat[]];
}
