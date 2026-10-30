"""SQLite tables (SQLModel). The schema grows per ticket; see the plan, section 2.3."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import JSON, Column, Dialect, String
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

from app.llm.schemas import PackageDraft
from app.planning.products import PlanningProducts
from app.playbook.engine import Status
from app.playbook.rules import EntityKind
from app.replay.diff import AdvisoryChanges
from app.risk.confidence import Confidence

ItemKind = Literal["gap", "conflict", "proposal"]
FieldStatus = Literal["done", "blocked"]
ItemStatus = Literal["pending", "approved", "overridden", "deferred", "alternative", "not_decided"]
PackageStatus = Literal["open", "closed"]
ModelVersionStatus = Literal["shadow", "proposed", "approved"]
ModelVersionKind = Literal["curves", "challenger"]


class Payload[M: BaseModel](TypeDecorator[M]):
    """A JSON column written and read through one pydantic model."""

    impl = JSON
    cache_ok = True

    def __init__(self, model: type[M]) -> None:
        super().__init__()
        self.model = model

    def process_bind_param(self, value: M | None, dialect: Dialect) -> Any:
        return None if value is None else value.model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> M | None:
        return None if value is None else self.model.model_validate(value)


class Asset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    x_km: float
    y_km: float
    elevation_m: float | None
    distance_to_coast_km: float
    install_year: int
    condition_score: int
    last_inspection_date: date
    customers_served: int
    district: str


class Dependency(SQLModel, table=True):
    from_id: str = Field(primary_key=True)
    to_id: str = Field(primary_key=True)
    to_kind: str


class Facility(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    x_km: float
    y_km: float


class StagingArea(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    x_km: float
    y_km: float
    elevation_m: float
    distance_to_coast_km: float
    district: str


class FragilityCurve(SQLModel, table=True):
    asset_type: str = Field(primary_key=True)
    hazard: str = Field(primary_key=True)
    theta: float
    beta: float


class ModelVersion(SQLModel, table=True):
    """A model risk scoring can use: a set of fragility curves or the challenger. Version 1 is
    the published curves; a calibration run proposes a new set. The challenger starts in shadow
    and is proposed only when it passes the promotion rule. Only an approved version is ever
    used to rank."""

    id: int | None = Field(default=None, primary_key=True)
    label: str
    kind: ModelVersionKind = Field(default="curves", sa_type=String)
    status: ModelVersionStatus = Field(sa_type=String)
    curves: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))  # [] if challenger
    created_at: datetime
    approved_by: str | None = None  # a role, or "published" for version 1
    approved_at: datetime | None = None
    backtest: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))  # before and after


class HistoricalStorm(SQLModel, table=True):
    """A past storm's best track, for the calibration back-test."""

    name: str = Field(primary_key=True)
    landfall_at: datetime
    landfall_t_hours: float  # track time of landfall
    landfall_x_km: float
    landfall_y_km: float
    peak_surge_m: float
    track: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))


class StormOutcome(SQLModel, table=True):
    """Whether an asset failed in a past storm."""

    storm: str = Field(primary_key=True, foreign_key="historicalstorm.name")
    asset_id: str = Field(primary_key=True, foreign_key="asset.id")
    failed: bool


class OpState(SQLModel, table=True):
    """Operational state per entity (asset, staging area, or "event") and key."""

    entity: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    value: Any = Field(sa_column=Column(JSON, nullable=False))
    set_by: str
    set_at: datetime


class Lineage(SQLModel, table=True):
    """One row per loaded gold file."""

    file: str = Field(primary_key=True)
    sha256: str
    loaded_at: datetime
    rows_ok: int
    rows_rejected: int


class QualityIssue(SQLModel, table=True):
    """A row the loader rejected, and why."""

    id: int | None = Field(default=None, primary_key=True)
    file: str = Field(foreign_key="lineage.file")
    row: int
    record_id: str | None
    reason: str


class Advisory(SQLModel, table=True):
    advisory_no: int = Field(primary_key=True)
    issued_at: datetime
    hours_to_landfall: int
    landfall_x_km: float
    landfall_y_km: float
    peak_surge_m: float
    track: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    cone_radius_km: dict[str, float] = Field(sa_column=Column(JSON, nullable=False))


class Coastline(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    coastline: list[list[float]] = Field(sa_column=Column(JSON, nullable=False))
    land: list[list[float]] = Field(sa_column=Column(JSON, nullable=False))


class ScenarioState(SQLModel, table=True):
    """Where the replay stands. current_advisory 0 means before advisory 1."""

    id: int = Field(default=1, primary_key=True)
    current_advisory: int = 0


class Exposure(SQLModel, table=True):
    """Hazard exposure per site (asset or staging area) and advisory: ensemble P50 / P90."""

    site_id: str = Field(primary_key=True)
    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    site_kind: str
    wind_p50_mph: float
    wind_p90_mph: float
    flood_depth_p50_m: float
    flood_depth_p90_m: float
    tsforce_arrival_h: float | None  # median hours from issue until wind >= 39 mph
    elevation_imputed: bool


class Score(SQLModel, table=True):
    """Risk per asset and advisory, with the factor breakdown that reproduces it."""

    asset_id: str = Field(primary_key=True, foreign_key="asset.id")
    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    model_version: int = Field(foreign_key="modelversion.id")  # the champion that scored it
    p_wind: float
    p_flood: float
    p_fail: float
    consequence: float  # customer-equivalents
    risk: float  # p_fail x consequence
    rank: int
    confidence: Confidence = Field(sa_type=String)
    confidence_reasons: list[str] = Field(sa_column=Column(JSON, nullable=False))
    factors: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class ShadowScore(SQLModel, table=True):
    """A challenger's score of an asset at an advisory, stored beside the champion's with the
    challenger's model version. It never drives the ranking, the playbook check or the package."""

    asset_id: str = Field(primary_key=True, foreign_key="asset.id")
    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    model_version: int = Field(primary_key=True, foreign_key="modelversion.id")
    p_fail: float
    risk: float  # p_fail x the champion's consequence
    rank: int  # by this model's risk
    factors: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class Finding(SQLModel, table=True):
    """The result of evaluating one playbook rule for one entity at one advisory."""

    id: int | None = Field(default=None, primary_key=True)
    advisory_no: int = Field(foreign_key="advisory.advisory_no")
    rule_id: str
    entity_id: str  # asset, staging area or "event"
    entity_kind: EntityKind = Field(sa_type=String)
    status: Status = Field(sa_type=String)
    severity: str
    owner_role: str
    cites: list[str] = Field(sa_column=Column(JSON, nullable=False))
    overdue: bool
    details: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class Alert(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    advisory_no: int = Field(foreign_key="advisory.advisory_no")
    asset_id: str = Field(foreign_key="asset.id")
    kind: str  # risk_threshold | top_n_entry | rank_jump
    message: str


class DecisionPackage(SQLModel, table=True):
    """Everything put before the EOC for one advisory (glossary: decision package)."""

    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    status: PackageStatus = Field(sa_type=String)
    changes: AdvisoryChanges = Field(sa_column=Column(Payload(AdvisoryChanges), nullable=False))
    # The draft situation report; None until the cycle has written it.
    draft: PackageDraft | None = Field(default=None, sa_column=Column(Payload(PackageDraft)))
    opened_at: datetime
    closed_at: datetime | None = None


class PackageItem(SQLModel, table=True):
    """One gap with its proposed action, one conflict, or one activation proposal (P-2.5),
    awaiting a person's decision."""

    id: int | None = Field(default=None, primary_key=True)
    advisory_no: int = Field(foreign_key="decisionpackage.advisory_no")
    finding_id: int = Field(foreign_key="finding.id")
    rule_id: str
    entity_id: str
    kind: ItemKind = Field(sa_type=String)
    proposed_action: str
    owner_role: str
    status: ItemStatus = Field(sa_type=String)
    decided_by: str | None = None
    reason: str | None = None
    decided_at: datetime | None = None
    # A field supervisor's note when the same work, approved in an earlier package, was
    # reported blocked (CR-02 C2): the gap is back because the work was not done.
    blocked_note: str | None = None


class FieldReport(SQLModel, table=True):
    """A field supervisor's report on a field task (an approved item that needs field work):
    done, or blocked with a note. The latest report counts; done is final."""

    item_id: int = Field(primary_key=True, foreign_key="packageitem.id")
    advisory_no: int  # the advisory in force when it was reported
    status: FieldStatus = Field(sa_type=String)
    note: str | None
    reported_at: datetime


class AuditEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recorded_at: datetime  # wall-clock time
    advisory_no: int | None  # scenario time: the advisory in force
    hours_to_landfall: int | None
    actor: str  # system | agent | human
    type: str
    summary: str
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    input_hash: str
    versions: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class Sitrep(SQLModel, table=True):
    """The situation report as the Incident Commander approved it (the draft stays on the
    decision package)."""

    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    approved_text: str
    approved_by: str
    approved_at: datetime
    edited: bool  # the approver changed the draft text


class PlanningDraft(SQLModel, table=True):
    """The ICS-215 and IAP objectives drafted for the operational period after an advisory. It
    stays DRAFT until the Planning Section Chief and then the commanding role approve it."""

    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    products: PlanningProducts = Field(sa_column=Column(Payload(PlanningProducts), nullable=False))
    drafted_at: datetime
    planning_approved_at: datetime | None = None
    released_by: str | None = None  # the commanding role
    released_at: datetime | None = None


SpanKind = Literal["cycle_node", "generation"]
SpanStatus = Literal["ok", "error", "paused"]
ValidationResult = Literal["passed", "failed", "error"]


class TraceSpan(SQLModel, table=True):
    """One finished OpenTelemetry span: an advisory-cycle node, or a grounded generation (the
    situation report draft, a copilot turn, the IAP objectives). Observability only: the audit
    log stays the record of what happened and who decided (decisions.md)."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: str  # the demo run: a backend start or a scenario reset begins a new one
    trace_id: str
    span_id: str
    parent_span_id: str | None
    advisory_no: int | None
    kind: SpanKind = Field(sa_type=String)
    node: str  # the cycle node, or the generation task
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    status: SpanStatus = Field(sa_type=String)
    provider: str | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None  # None when a model with tokens has no price in llm.yaml
    retries: int = 0
    fallback: bool = False
    fallback_reason: str | None = None
    validation: ValidationResult | None = Field(default=None, sa_type=String)
    attempts: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
