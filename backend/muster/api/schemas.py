"""Response models for the HTTP API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from muster.advisory_context import Commander
from muster.agent.decisions import Action, Role
from muster.agent.field import TaskStatus
from muster.audit.log import Actor
from muster.hazard.ensemble import SiteKind
from muster.ingest.contracts import AssetType, FacilityType
from muster.llm.schemas import PackageDraft
from muster.models import (
    ItemKind,
    ItemStatus,
    PackageStatus,
    SpanKind,
    SpanStatus,
    ValidationResult,
)
from muster.planning.products import PlanningProducts, PlanningStatus
from muster.playbook.activation import Level
from muster.playbook.engine import Status
from muster.playbook.rules import EntityKind
from muster.replay.diff import AdvisoryChanges
from muster.risk.alerts import AlertKind
from muster.risk.bands import TopFactor
from muster.risk.confidence import Confidence
from muster.scoring_config import IntensityCategory, RiskBand


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


class DistrictOut(BaseModel):
    name: str
    west_km: float
    east_km: float
    label: PointOut  # where the maps write its name
    boundary: list[PointOut]  # where it meets its western neighbour; [] for the westernmost


class RiskItemOut(BaseModel):
    asset_id: str
    p_fail: float
    consequence: float  # customer-equivalents
    risk: float  # p_fail x consequence
    rank: int
    previous_rank: int | None  # None at the first advisory
    confidence: Confidence
    risk_band: RiskBand  # from p_fail (config/scoring.yaml)
    top_factor: TopFactor  # the hazard with the higher p_fail on its own


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


class ChallengerFeatureOut(BaseModel):
    feature: str  # one of the challenger's features (muster/challenger/dataset.py FEATURES)
    value: float | str  # the asset type is a category
    contribution: float  # p_fail minus p_fail with this feature alone at the training baseline


class ChallengerViewOut(BaseModel):
    """The challenger's shadow score of an asset at an advisory, beside the champion's."""

    model_version: int
    rank: int
    p_fail: float
    top_features: list[ChallengerFeatureOut]  # config/models.yaml challenger.explain_features


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
    challenger: ChallengerViewOut | None  # None when no challenger scored it in shadow


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


class ToolCallOut(BaseModel):
    name: str
    args: dict[str, Any]
    result: dict[str, Any]  # as the model was shown it: restricted fields already filtered


class AttemptOut(BaseModel):
    """One try of the configured provider, as the audit event records it."""

    provider: str
    model: str | None
    prompt_version: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    problems: list[str]  # what the validator found; empty when it passed
    error: str | None  # the provider failed; no result was validated


class WorkOut(BaseModel):
    """How the copilot got its answer: the "how I got this" panel."""

    tool_calls: list[ToolCallOut]  # the answering turn's calls
    attempts: list[AttemptOut]
    retries: int
    validated: bool  # the answer passed the validator; False when the template replaced it
    provider: str
    model: str | None
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # None: tokens from a model with no price in config/llm.yaml
    fallback: bool
    fallback_reason: str | None


class ChatOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    provider: str  # the provider that answered, or "template (fallback)"
    fallback: bool
    tools_used: list[str]
    advisory: int | None  # the advisory the answer is about: the current one; None before 1
    work: WorkOut


class StepOut(BaseModel):
    """One step of a copilot turn as it happens (a server-sent `step` event). Never answer text."""

    kind: Literal[
        "attempt", "validating", "validated", "rejected", "failed", "fallback", "tool_call"
    ]
    attempt: int
    provider: str
    problems: list[str]
    reason: str | None
    tool: str | None
    args: dict[str, Any]


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
    kind: Literal["curves", "challenger"]
    status: Literal["shadow", "proposed", "approved"]
    in_use: bool  # the champion (the latest approved): ranks the next advisory
    curves: list[CurveOut]  # empty for the challenger
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


class PlanningOut(PlanningProducts):
    """The ICS-215 and IAP objectives drafted for the period after an advisory, DRAFT until
    the Planning Section Chief approves and the commanding role releases them."""

    advisory_no: int
    status: PlanningStatus
    drafted_at: datetime
    planning_approved_at: datetime | None
    released_by: str | None
    released_at: datetime | None


class PlanningReleaseIn(BaseModel):
    role: Role


class TraceSpanOut(BaseModel):
    """One span of the run trace: an advisory-cycle node or a grounded generation."""

    span_id: str
    parent_span_id: str | None  # a generation's node, or a span not stored (the HTTP request)
    advisory_no: int | None
    kind: SpanKind
    node: str  # the cycle node, or the generation task (sitrep_draft, copilot, iap_objectives)
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    status: SpanStatus  # paused: await_approval waiting for decisions
    provider: str | None  # the provider that produced the result, or "template (fallback)"
    model: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float | None  # None: tokens from a model with no price in config/llm.yaml
    retries: int
    fallback: bool
    fallback_reason: str | None
    validation: ValidationResult | None  # generations only
    attempts: list[dict[str, Any]]


class TraceTotalsOut(BaseModel):
    latency_ms: float  # top-level spans: a generation is inside its node's time
    tokens_in: int
    tokens_out: int
    cost_usd: float
    unpriced_spans: int
    retries: int
    fallbacks: int


class RunTraceOut(BaseModel):
    run_id: str  # the demo run since the backend started or the scenario was reset
    advisory_no: int
    spans: list[TraceSpanOut]
    advisory_totals: TraceTotalsOut
    run_totals: TraceTotalsOut


class ModelMetricsOut(BaseModel):
    assets: int
    failures: int
    brier: float
    roc_auc: float | None  # None when every asset had the same outcome
    top_fraction: float
    top_capture: float
    reliability: list[ReliabilityBinOut]


class PromotionCriterionOut(BaseModel):
    name: Literal["brier_improvement", "top_capture_gain", "calibration_error"]
    value: float  # the challenger's margin over the champion, or its calibration error
    threshold: float  # config/models.yaml promotion
    passed: bool


class PromotionCheckOut(BaseModel):
    storm: str  # the held-out storm the rule is checked on
    passed: bool  # the challenger may be proposed
    criteria: list[PromotionCriterionOut]


class ChallengerOut(BaseModel):
    model_version: ModelVersionOut
    challenger: ModelMetricsOut  # on the held-out storm
    champion: ModelMetricsOut  # the published curves on the same storm
    promotion: PromotionCheckOut


class DisagreementOut(BaseModel):
    asset_id: str
    asset_name: str
    challenger_rank: int
    champion_rank: int
    challenger_p_fail: float
    champion_p_fail: float
    top_features: list[ChallengerFeatureOut]  # why the challenger ranks it higher


class DisagreementsOut(BaseModel):
    """Assets the challenger ranks in its top N at an advisory that the champion does not."""

    advisory_no: int
    model_version: int  # the challenger's
    top_n: int  # config/scoring.yaml risk.top_n
    items: list[DisagreementOut]  # by the challenger's rank; empty when it is the champion
