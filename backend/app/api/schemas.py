"""Response models for the HTTP API."""

from datetime import date, datetime

from pydantic import BaseModel

from app.ingest.contracts import AssetType, FacilityType


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
    score: float
    rank: int
    previous_rank: int | None  # None at the first advisory


class RiskListOut(BaseModel):
    advisory_no: int
    items: list[RiskItemOut]
