# Generated from packages/schemas by scripts/gen_schemas.sh. DO NOT EDIT.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    insufficient_data = "insufficient_data"


class JobType(StrEnum):
    noop = "noop"


class Job(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    type: JobType
    status: JobStatus
    priority: int
    attempts: Annotated[int, Field(ge=0)]
    max_attempts: Annotated[int, Field(ge=1)]
    cancel_requested: bool
    error: str | None = None
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None


class Level(StrEnum):
    low = "low"
    moderate = "moderate"
    high = "high"


class Confidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    level: Level
    basis: Annotated[
        str,
        Field(
            description="Why this level: data quality, concordant evidence lines, validation status, coverage.",
            min_length=1,
        ),
    ]


class Status(StrEnum):
    quantified = "quantified"


class QuantifiedUncertainty(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status
    method: Annotated[str, Field(min_length=1)]
    value: float
    unit: str | None = None


class Status1(StrEnum):
    not_quantified = "not_quantified"


class NotQuantifiedUncertainty(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status1
    reason: Annotated[str, Field(min_length=1)]


class Uncertainty(RootModel[QuantifiedUncertainty | NotQuantifiedUncertainty]):
    root: QuantifiedUncertainty | NotQuantifiedUncertainty


class SupportingItem(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class CounterEvidenceItem(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class Limitation(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class Explanation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    summary: Annotated[str, Field(min_length=1)]
    supporting: list[SupportingItem]
    counter_evidence: list[CounterEvidenceItem]
    limitations: Annotated[list[Limitation], Field(min_length=1)]


class Via(StrEnum):
    stac = "stac"
    earth_engine = "earth_engine"
    direct = "direct"
    user_upload = "user_upload"


class Source(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    dataset: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    acquired: Annotated[
        str, Field(description="Acquisition date or interval (ISO 8601).", min_length=1)
    ]
    licence: Annotated[str, Field(min_length=1)]
    url: str | None = None
    via: Via | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    run_id: Annotated[str, Field(min_length=1)]
    code_version: Annotated[str, Field(min_length=1)]
    parameters: dict[str, Any]
    created_at: AwareDatetime
    aoi_hash: str | None = None
    crs: str | None = None
    dependency_versions: dict[str, str] | None = None


class Basis(StrEnum):
    field_geophysics = "field_geophysics"
    direct_verification = "direct_verification"


class Depth(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    basis: Basis
    method: Annotated[str, Field(min_length=1)]
    value_m: float
    uncertainty_m: Annotated[float, Field(ge=0.0)]


class Kind(StrEnum):
    prospectivity = "prospectivity"
    anomaly = "anomaly"
    evidence = "evidence"
    geophysics_model = "geophysics_model"


class DisclaimerId(StrEnum):
    D_1 = "D-1"
    D_2 = "D-2"


class ValidationStatus(StrEnum):
    unvalidated = "unvalidated"


class CalibrationStatus(StrEnum):
    uncalibrated = "uncalibrated"
    calibrated = "calibrated"


class EngineStatus(StrEnum):
    experimental = "experimental"
    validated = "validated"


class DepositModel(StrEnum):
    orogenic = "orogenic"


class Applicability(StrEnum):
    applicable = "applicable"
    applicability_unknown = "applicability_unknown"


class ResultEnvelope(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    kind: Kind
    value: float | str | None
    confidence: Confidence
    uncertainty: Uncertainty
    explanation: Explanation
    sources: Annotated[list[Source], Field(min_length=1)]
    provenance: Provenance
    disclaimer_id: DisclaimerId
    validation_status: ValidationStatus
    calibration_status: CalibrationStatus
    engine_status: EngineStatus
    deposit_model: DepositModel | None = None
    applicability: Applicability | None = None
    depth: Depth | None = None


class GeoContracts(BaseModel):
    job: Job | None = None
    result_envelope: ResultEnvelope | None = None
