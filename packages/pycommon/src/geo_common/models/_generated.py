# Generated from packages/schemas by scripts/gen_schemas.sh. DO NOT EDIT.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal
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
    catalog_search = "catalog_search"


class Job(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    type: JobType
    aoi_id: Annotated[
        UUID | None,
        Field(description="Target AOI of an AOI-bound job (catalog_search); null for noop."),
    ] = None
    project_id: Annotated[
        UUID | None,
        Field(description="Derived from the AOI by the server, never supplied by the client; null for noop."),
    ] = None
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
    acquired: Annotated[str, Field(description="Acquisition date or interval (ISO 8601).", min_length=1)]
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


class AoiMethod(StrEnum):
    point_radius = "point_radius"
    rectangle = "rectangle"
    polygon = "polygon"
    geojson = "geojson"
    kml = "kml"
    kmz = "kmz"
    shapefile = "shapefile"


class LonLat(RootModel[list[float]]):
    root: Annotated[
        list[float],
        Field(description="[longitude, latitude] in EPSG:4326", max_length=2, min_length=2),
    ]


class Type(StrEnum):
    Polygon = "Polygon"


class GeoJsonPolygon(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: Type
    coordinates: list[list[LonLat]]


class Bbox(RootModel[list[float]]):
    root: Annotated[
        list[float],
        Field(description="[west, south, east, north]", max_length=4, min_length=4),
    ]


class AoiName(RootModel[str]):
    root: Annotated[str, Field(max_length=120, min_length=1)]


class AoiPointRadiusRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    method: Literal["point_radius"]
    name: AoiName | None = None
    lat: float
    lon: float
    radius_m: float
    project_id: Annotated[UUID | None, Field(description="Required to save; ignored by preview.")] = None


class AoiRectangleRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    method: Literal["rectangle"]
    name: AoiName | None = None
    west: float
    south: float
    east: float
    north: float
    project_id: Annotated[UUID | None, Field(description="Required to save; ignored by preview.")] = None


class AoiPolygonRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    method: Literal["polygon"]
    name: AoiName | None = None
    coordinates: Annotated[
        list[LonLat],
        Field(
            description="Outer ring only; open rings are closed automatically.",
            min_length=3,
        ),
    ]
    project_id: Annotated[UUID | None, Field(description="Required to save; ignored by preview.")] = None


class AoiDraft(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    method: AoiMethod
    geometry: GeoJsonPolygon
    bbox: Bbox
    area_km2: float
    vertex_count: Annotated[int, Field(ge=3)]
    working_crs: str
    details: dict[str, Any]
    warnings: list[str]


class Aoi(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    name: AoiName
    method: AoiMethod
    geometry: GeoJsonPolygon
    bbox: Bbox
    area_km2: float
    vertex_count: Annotated[int, Field(ge=3)]
    working_crs: str
    details: dict[str, Any]
    warnings: list[str]
    created_at: AwareDatetime
    project_id: UUID


class AoiSummary(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    name: AoiName
    method: AoiMethod
    bbox: Bbox
    area_km2: float
    created_at: AwareDatetime
    project_id: UUID


class AoiList(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    items: list[AoiSummary]
    total: Annotated[int, Field(ge=0)]


class AoiLimits(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    max_area_km2: float
    min_area_km2: float
    max_radius_m: float
    max_vertices: int
    max_upload_mb: int
    max_stored_aois: int
    max_abs_latitude: float
    supported_upload_formats: list[str]
    max_projects: int


class ProjectName(RootModel[str]):
    root: Annotated[str, Field(max_length=120, min_length=1)]


class Project(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    name: ProjectName
    description: Annotated[str | None, Field(max_length=500)]
    aoi_count: Annotated[int, Field(ge=0)]
    created_at: AwareDatetime


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: ProjectName
    description: Annotated[str | None, Field(max_length=500)] = None


class ProjectList(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    items: list[Project]
    total: Annotated[int, Field(ge=0)]


class AssetKind(StrEnum):
    scene_catalog = "scene_catalog"
    dem_clip = "dem_clip"
    user_vector = "user_vector"


class Asset(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    project_id: UUID
    aoi_id: UUID
    job_id: UUID | None
    kind: AssetKind
    media_type: str
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
    created_at: AwareDatetime
    provenance: Annotated[
        dict[str, Any],
        Field(description="Source metadata: dataset, version, date, parameters, code version."),
    ]


class AssetList(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    items: list[Asset]
    total: Annotated[int, Field(ge=0)]


class AssetDeleted(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    deleted: Literal[True]
    files_pending_cleanup: Annotated[int, Field(ge=0)]


class GeoContracts(BaseModel):
    job: Job | None = None
    result_envelope: ResultEnvelope | None = None
    aoi: Aoi | None = None
    aoi_draft: AoiDraft | None = None
    aoi_list: AoiList | None = None
    aoi_limits: AoiLimits | None = None
    aoi_point_radius_request: AoiPointRadiusRequest | None = None
    aoi_rectangle_request: AoiRectangleRequest | None = None
    aoi_polygon_request: AoiPolygonRequest | None = None
    project: Project | None = None
    project_list: ProjectList | None = None
    project_create_request: ProjectCreateRequest | None = None
    asset: Asset | None = None
    asset_list: AssetList | None = None
    asset_deleted: AssetDeleted | None = None
