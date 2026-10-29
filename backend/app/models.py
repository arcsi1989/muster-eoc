"""SQLite tables (SQLModel). The schema grows per ticket; see the plan, section 2.3."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel

from app.playbook.engine import Status
from app.playbook.rules import EntityKind
from app.risk.confidence import Confidence


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


class FragilityCurve(SQLModel, table=True):
    asset_type: str = Field(primary_key=True)
    hazard: str = Field(primary_key=True)
    theta: float
    beta: float


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
    p_wind: float
    p_flood: float
    p_fail: float
    consequence: float  # customer-equivalents
    risk: float  # p_fail x consequence
    rank: int
    confidence: Confidence = Field(sa_type=String)
    confidence_reasons: list[str] = Field(sa_column=Column(JSON, nullable=False))
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
