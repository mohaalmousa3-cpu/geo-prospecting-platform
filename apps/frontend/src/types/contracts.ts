/* Generated from packages/schemas. DO NOT EDIT. */

/**
 * Phase 1 allows only the noop job. Later phases extend this enum.
 */
export type JobType = "noop";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled" | "insufficient_data";
export type Uncertainty = QuantifiedUncertainty | NotQuantifiedUncertainty;

/**
 * Shared contracts (ADR-0009, ADR-0010, ADR-0011). Single source of truth; Pydantic and TypeScript types are generated from this file.
 */
export interface GeoContracts {
  job?: Job;
  result_envelope?: ResultEnvelope;
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
