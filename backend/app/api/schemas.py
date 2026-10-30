"""Response models for the HTTP API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.advisory_context import Commander
from app.agent.decisions import Action, Role
from app.agent.field import TaskStatus
from app.audit.log import Actor
from app.hazard.ensemble import SiteKind
from app.ingest.contracts import AssetType, FacilityType
from app.llm.schemas import PackageDraft
from app.models import ItemKind, ItemStatus, PackageStatus
from app.playbook.activation import Level
from app.playbook.engine import Status
from app.playbook.rules import EntityKind
from app.replay.diff import AdvisoryChanges
from app.risk.alerts import AlertKind
from app.risk.confidence import Confidence
from app.scoring_config import IntensityCategory


class PointOut(BaseModel):
    x_km: float
    y_km: float


class StormPositionOut(BaseModel):
    """Where the storm is (or is forecast to be) at a time, with its intensity."""

    valid_at: datetime
    x_km: float
    y_km: float
    vmax_mph: float
    category: IntensityCategory  # Saffir-Simpson, from vmax_mph (config/scoring.yaml)


class TrackPointOut(StormPositionOut):
    t_hours: float  # lead time: valid_at is the issue time + t_hours
    rmax_km: float


class PastPositionOut(StormPositionOut):
    """Where the storm was when an earlier advisory was issued."""

    advisory_no: int


class AdvisoryOut(BaseModel):
    advisory_no: int
    issued_at: datetime
    hours_to_landfall: int
    activation_level: str | None
    max_wind_mph: float
    peak_surge_m: float
    landfall: PointOut
    track: list[TrackPointOut]  # forecast points
    past_positions: list[PastPositionOut]  # earlier advisories, oldest first
    cone: list[PointOut]  # outline of the NHC-style forecast cone


class TimelineSlotOut(BaseModel):
    """One advisory in the replay schedule; the forecast itself stays hidden until issued."""

    advisory_no: int
    hours_to_landfall: int
    activation_level: str | None
    issued: bool


class ScenarioOut(BaseModel):
    total_advisories: int
    current_advisory: int  # 0 before advisory 1
    timeline: list[TimelineSlotOut]
    advisories: list[AdvisoryOut]  # issued advisories only


class AssetOut(BaseModel):
    id: str
    name: str
    type: AssetType
    x_km: float
    y_km: float
    elevation_m: float | None
    distance_to_coast_km: float
    install_year: int
    condition_score: int
    last_inspection_date: date
    customers_served: int


class FacilityOut(BaseModel):
    id: str
    name: str
    type: FacilityType
    x_km: float
    y_km: float


class StagingAreaOut(BaseModel):
    id: str
    name: str
    x_km: float
    y_km: float
    elevation_m: float
    distance_to_coast_km: float


class QualityIssueOut(BaseModel):
    row: int
    record_id: str | None
    reason: str


class LineageOut(BaseModel):
    file: str
    sha256: str
    loaded_at: datetime
    rows_ok: int
    rows_rejected: int
    issues: list[QualityIssueOut]


class CoastlineOut(BaseModel):
    coastline: list[PointOut]
    land: list[PointOut]


class RiskItemOut(BaseModel):
    asset_id: str
    p_fail: float
    consequence: float  # customer-equivalents
    risk: float  # p_fail x consequence
    rank: int
    previous_rank: int | None  # None at the first advisory
    confidence: Confidence


class RiskListOut(BaseModel):
    advisory_no: int
    model_version: int  # the fragility curves that scored the advisory
    items: list[RiskItemOut]


class ExposureOut(BaseModel):
    site_id: str
    site_kind: SiteKind
    wind_p50_mph: float
    wind_p90_mph: float
    flood_depth_p50_m: float
    flood_depth_p90_m: float
    tsforce_arrival_h: float | None  # median hours until tropical-storm-force wind; None if never
    elevation_imputed: bool


class HazardFactorOut(BaseModel):
    theta: float  # published median capacity: mph for wind, m for flood
    theta_adjusted: float  # after the condition adjustment
    beta: float
    p_fail: float  # this hazard alone, mean over ensemble members


class DownstreamAssetOut(BaseModel):
    id: str
    customers: float  # share counted for this asset
    feeders: int


class WeightedFacilityOut(BaseModel):
    id: str
    type: str
    weight: float  # share counted for this asset
    feeders: int


class ConsequenceOut(BaseModel):
    own_customers: int
    downstream_assets: list[DownstreamAssetOut]
    facilities: list[WeightedFacilityOut]
    total: float


class DependencyLinkOut(BaseModel):
    id: str
    kind: Literal["asset", "facility"]
    name: str


class ExplainOut(BaseModel):
    asset: AssetOut
    advisory_no: int
    rank: int
    risk: float
    p_fail: float
    p_wind: float
    p_flood: float
    wind: HazardFactorOut
    flood: HazardFactorOut
    exposure: ExposureOut
    consequence: ConsequenceOut
    confidence: Confidence
    confidence_reasons: list[str]
    feeds: list[DependencyLinkOut]
    fed_by: list[DependencyLinkOut]


class AlertOut(BaseModel):
    asset_id: str
    kind: AlertKind
    message: str


class FindingOut(BaseModel):
    rule_id: str
    title: str
    entity_id: str
    entity_kind: EntityKind
    entity_name: str | None
    status: Status
    severity: str
    owner_role: str
    cites: list[str]
    overdue: bool
    details: dict[str, Any]


class ClauseOut(BaseModel):
    id: str
    section: str
    title: str
    text: str


class PackageItemOut(BaseModel):
    id: int
    rule_id: str
    title: str
    entity_id: str
    entity_name: str | None
    kind: ItemKind
    proposed_action: str
    owner_role: str
    severity: str
    cites: list[str]
    overdue: bool
    status: ItemStatus
    decided_by: str | None
    reason: str | None
    decided_at: datetime | None
    blocked_note: str | None  # the same work, approved earlier, was reported blocked


class SitrepOut(BaseModel):
    advisory_no: int
    approved_text: str
    approved_by: str
    approved_at: datetime
    edited: bool


class SitrepApproveIn(BaseModel):
    role: Role
    text: str


class PackageOut(BaseModel):
    advisory_no: int
    status: PackageStatus
    activation_level: str | None  # declared (P-2.5)
    proposed_activation_level: str | None  # from the playbook's thresholds
    decides_as_commander: Commander
    changes: AdvisoryChanges
    items: list[PackageItemOut]
    draft: PackageDraft | None
    draft_text: str | None  # the draft as editable plain text
    sitrep: SitrepOut | None  # the approved situation report, once approved


class DecisionIn(BaseModel):
    role: Role
    action: Action
    reason: str | None = None


class FieldReportIn(BaseModel):
    district: str  # the supervisor's own district
    note: str | None = None


class FieldTaskOut(BaseModel):
    """An approved item that needs field work, as a field supervisor sees it."""

    item_id: int
    approved_in: int  # the advisory whose package approved it
    rule_id: str
    why: str
    action: str
    entity_id: str
    entity_name: str | None
    approved_by: str | None
    approved_at: datetime | None
    stop_work: list[str]  # prohibitions in force at the site now (P-4.7); Done is refused
    status: TaskStatus
    note: str | None
    reported_at: datetime | None


class DeclarationIn(BaseModel):
    level: Level
    declared_by: Role
    reason: str | None = None


class AuditEventOut(BaseModel):
    id: int
    recorded_at: datetime  # wall-clock time
    advisory_no: int | None  # scenario time
    hours_to_landfall: int | None
    actor: Actor
    type: str
    summary: str
    payload: dict[str, Any]
    input_hash: str
    versions: dict[str, Any]


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurnIn] = Field(default=[], max_length=20)  # copilot.history_max


class CitationOut(BaseModel):
    id: str
    kind: Literal["asset", "clause"]


class ChatOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    provider: str  # the provider that answered, or "template (fallback)"
    fallback: bool
    tools_used: list[str]


class CurveOut(BaseModel):
    asset_type: str
    hazard: Literal["wind", "flood"]
    theta: float  # median capacity: mph for wind, m for flood
    beta: float


class ReliabilityBinOut(BaseModel):
    lower: float
    upper: float
    count: int
    mean_predicted: float | None  # None for an empty bin
    observed_rate: float | None


class BacktestOut(BaseModel):
    model_version: int
    assets: int
    failures: int
    brier: float
    top_fraction: float  # of assets, by predicted probability (calibration.top_fraction)
    top_capture: float  # share of all failures among them (top-decile capture at 0.10)
    reliability: list[ReliabilityBinOut]


class ModelVersionOut(BaseModel):
    id: int
    label: str
    status: Literal["proposed", "approved"]
    in_use: bool  # the latest approved: scores the next advisory
    curves: list[CurveOut]
    created_at: datetime
    approved_by: str | None
    approved_at: datetime | None


class CalibrationOut(BaseModel):
    storm: str
    before: BacktestOut  # the version in use
    after: BacktestOut  # the proposed version
    model_version: ModelVersionOut


class ModelVersionApproveIn(BaseModel):
    role: Role
