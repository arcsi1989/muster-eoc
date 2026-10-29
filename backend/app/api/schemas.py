"""Response models for the HTTP API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.decisions import Action, Role
from app.hazard.ensemble import SiteKind
from app.ingest.contracts import AssetType, FacilityType
from app.playbook.engine import Status
from app.playbook.rules import EntityKind
from app.risk.alerts import AlertKind
from app.risk.confidence import Confidence


class PointOut(BaseModel):
    x_km: float
    y_km: float


class TrackPointOut(BaseModel):
    t_hours: float
    x_km: float
    y_km: float
    vmax_mph: float
    rmax_km: float


class AdvisoryOut(BaseModel):
    advisory_no: int
    issued_at: datetime
    hours_to_landfall: int
    activation_level: str | None
    max_wind_mph: float
    peak_surge_m: float
    landfall: PointOut
    track: list[TrackPointOut]
    cone: list[PointOut]  # outline of the forecast cone


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


class LandfallShiftOut(BaseModel):
    distance_km: float
    direction: str


class RankMoveOut(BaseModel):
    asset_id: str
    from_rank: int
    to_rank: int


class ChangesOut(BaseModel):
    advisory_no: int
    previous_advisory_no: int | None  # None at the first advisory: everything is initial
    landfall_shift: LandfallShiftOut | None
    max_wind_change_mph: float | None
    peak_surge_change_m: float | None
    activation_level_from: str | None
    activation_level_to: str | None
    top10_entered: list[str]
    top10_left: list[str]
    rank_moves: list[RankMoveOut]  # biggest move first


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
    kind: Literal["gap", "conflict"]
    proposed_action: str
    owner_role: str
    severity: str
    cites: list[str]
    overdue: bool
    status: Literal["pending", "approved", "overridden", "deferred", "alternative", "not_decided"]
    decided_by: str | None
    reason: str | None
    decided_at: datetime | None


class DraftParagraphOut(BaseModel):
    text: str
    clause_ids: list[str]
    asset_ids: list[str]


class DraftSectionOut(BaseModel):
    heading: str
    paragraphs: list[DraftParagraphOut]


class DraftOut(BaseModel):
    status: str  # DRAFT until approved
    provider: str  # the provider that wrote it, or "template (fallback)"
    fallback: bool  # the template draft replaced the provider's draft
    model: str | None
    prompt_version: str | None  # None for template drafts: no prompt is used
    fallback_reason: str | None
    sections: list[DraftSectionOut]


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
    status: Literal["open", "closed"]
    activation_level: str | None
    decides_as_commander: Literal["incident_commander", "director"]
    changes: ChangesOut
    items: list[PackageItemOut]
    draft: DraftOut | None
    draft_text: str | None  # the draft as editable plain text
    sitrep: SitrepOut | None  # the approved situation report, once approved


class DecisionIn(BaseModel):
    role: Role
    action: Action
    reason: str | None = None


class AuditEventOut(BaseModel):
    id: int
    recorded_at: datetime  # wall-clock time
    advisory_no: int | None  # scenario time
    hours_to_landfall: int | None
    actor: Literal["system", "agent", "human"]
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
