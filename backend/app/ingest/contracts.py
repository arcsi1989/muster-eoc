"""Data contracts for the gold files (docs/IMPLEMENTATION_PLAN.md section 2.1).

Coordinates are planar km on the fictional territory (`x_km`, `y_km`), not longitude/latitude
(docs/decisions.md). JSON Schemas exported from these models live in `contracts/`.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["substation", "pump_station", "treatment_plant"]
FacilityType = Literal["hospital", "shelter"]
Hazard = Literal["wind", "flood"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetRecord(Contract):
    id: str = Field(pattern=r"^(SUB|PS|WTP)-\d{2,3}$")
    name: str = Field(min_length=1)
    type: AssetType
    x_km: float
    y_km: float
    elevation_m: float | None  # null on purpose for a few rows: imputed, lowers confidence
    distance_to_coast_km: float = Field(ge=0)
    install_year: int = Field(ge=1900, le=2026)
    condition_score: int = Field(ge=1, le=5)  # 1 good ... 5 very poor
    last_inspection_date: date
    customers_served: int = Field(ge=0)


class DependencyRecord(Contract):
    from_id: str
    to_id: str
    to_kind: Literal["asset", "facility"]


class FacilityRecord(Contract):
    id: str = Field(pattern=r"^(HOSP|SHEL)-\d{2}$")
    name: str = Field(min_length=1)
    type: FacilityType
    x_km: float
    y_km: float


class StagingAreaRecord(Contract):
    id: str = Field(pattern=r"^STG-\d{2}$")
    name: str = Field(min_length=1)
    x_km: float
    y_km: float
    elevation_m: float
    distance_to_coast_km: float = Field(ge=0)


class FragilityCurveRecord(Contract):
    """Published lognormal fragility curve: P(fail | x) = Phi(ln(x / theta) / beta)."""

    asset_type: AssetType
    hazard: Hazard
    theta: float = Field(gt=0)  # median capacity: mph for wind, m for flood
    beta: float = Field(gt=0)  # dispersion


class InitialStateFile(Contract):
    """Operational state at advisory 1: per-entity flags and event-level values."""

    entities: dict[str, dict[str, bool]]
    event: dict[str, int | bool | str]


class PointRecord(Contract):
    x_km: float
    y_km: float


class TrackPointRecord(Contract):
    t_hours: float = Field(ge=0)
    x_km: float
    y_km: float
    vmax_mph: float = Field(gt=0)
    rmax_km: float = Field(gt=0)


class AdvisoryRecord(Contract):
    advisory_no: int = Field(ge=1)
    issued_at: datetime
    hours_to_landfall: int = Field(ge=0)
    track: list[TrackPointRecord] = Field(min_length=2)
    cone_radius_km: dict[str, float]  # by lead time in hours
    landfall: PointRecord
    peak_surge_m: float = Field(ge=0)


class HistoricalStormFile(Contract):
    """A past storm's best track (history/), for the calibration back-test. `landfall_t_hours` is
    the track time of landfall."""

    name: str = Field(min_length=1)
    landfall_at: datetime
    landfall_t_hours: float = Field(ge=0)
    track: list[TrackPointRecord] = Field(min_length=2)
    landfall: PointRecord
    peak_surge_m: float = Field(ge=0)


class StormOutcomeRecord(Contract):
    """Whether an asset failed in the past storm."""

    asset_id: str
    failed: bool


class LineStringGeometry(Contract):
    type: Literal["LineString"]
    coordinates: list[tuple[float, float]]


class PolygonGeometry(Contract):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]


class CoastlineFeature(Contract):
    type: Literal["Feature"]
    properties: dict[str, str]
    geometry: LineStringGeometry | PolygonGeometry = Field(discriminator="type")


class CoastlineFile(Contract):
    """GeoJSON with planar km coordinates ([x_km, y_km]) instead of longitude/latitude."""

    type: Literal["FeatureCollection"]
    features: list[CoastlineFeature]
