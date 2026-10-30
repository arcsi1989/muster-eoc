"""Data contracts for the gold files (docs/IMPLEMENTATION_PLAN.md section 2.1).

Coordinates are planar km on the fictional territory (`x_km`, `y_km`), not longitude/latitude
(docs/decisions.md). JSON Schemas exported from these models live in `contracts/`.

Every field carries its data class (PRD section 08, CR-03 C1): `public` (published anyway: the
forecast, the fragility curves), `internal` (SGW's own operational data) or `restricted`
(coordinates, elevation and the dependency graph). Restricted fields never reach a model; maps
and coordinates stay in the UI (`app.classification`).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

AssetType = Literal["substation", "pump_station", "treatment_plant"]
FacilityType = Literal["hospital", "shelter"]
Hazard = Literal["wind", "flood"]
DataClass = Literal["public", "internal", "restricted"]

# Field metadata: the data class of a contract field, also written to its JSON Schema.
PUBLIC: JsonDict = {"data_class": "public"}
INTERNAL: JsonDict = {"data_class": "internal"}
RESTRICTED: JsonDict = {"data_class": "restricted"}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetRecord(Contract):
    id: str = Field(pattern=r"^(SUB|PS|WTP)-\d{2,3}$", json_schema_extra=INTERNAL)
    name: str = Field(min_length=1, json_schema_extra=INTERNAL)
    type: AssetType = Field(json_schema_extra=INTERNAL)
    x_km: float = Field(json_schema_extra=RESTRICTED)
    y_km: float = Field(json_schema_extra=RESTRICTED)
    # null on purpose for a few rows: imputed, lowers confidence
    elevation_m: float | None = Field(json_schema_extra=RESTRICTED)
    distance_to_coast_km: float = Field(ge=0, json_schema_extra=INTERNAL)
    install_year: int = Field(ge=1900, le=2026, json_schema_extra=INTERNAL)
    condition_score: int = Field(ge=1, le=5, json_schema_extra=INTERNAL)  # 1 good ... 5 very poor
    last_inspection_date: date = Field(json_schema_extra=INTERNAL)
    customers_served: int = Field(ge=0, json_schema_extra=INTERNAL)
    # the fictional area a field supervisor works
    district: str = Field(min_length=1, json_schema_extra=INTERNAL)


class DependencyRecord(Contract):
    """One edge of the dependency graph: restricted, field by field."""

    from_id: str = Field(json_schema_extra=RESTRICTED)
    to_id: str = Field(json_schema_extra=RESTRICTED)
    to_kind: Literal["asset", "facility"] = Field(json_schema_extra=RESTRICTED)


class FacilityRecord(Contract):
    id: str = Field(pattern=r"^(HOSP|SHEL)-\d{2}$", json_schema_extra=INTERNAL)
    name: str = Field(min_length=1, json_schema_extra=INTERNAL)
    type: FacilityType = Field(json_schema_extra=INTERNAL)
    x_km: float = Field(json_schema_extra=RESTRICTED)
    y_km: float = Field(json_schema_extra=RESTRICTED)


class StagingAreaRecord(Contract):
    id: str = Field(pattern=r"^STG-\d{2}$", json_schema_extra=INTERNAL)
    name: str = Field(min_length=1, json_schema_extra=INTERNAL)
    x_km: float = Field(json_schema_extra=RESTRICTED)
    y_km: float = Field(json_schema_extra=RESTRICTED)
    elevation_m: float = Field(json_schema_extra=RESTRICTED)
    distance_to_coast_km: float = Field(ge=0, json_schema_extra=INTERNAL)
    district: str = Field(min_length=1, json_schema_extra=INTERNAL)


class FragilityCurveRecord(Contract):
    """Published lognormal fragility curve: P(fail | x) = Phi(ln(x / theta) / beta)."""

    asset_type: AssetType = Field(json_schema_extra=PUBLIC)
    hazard: Hazard = Field(json_schema_extra=PUBLIC)
    # median capacity: mph for wind, m for flood
    theta: float = Field(gt=0, json_schema_extra=PUBLIC)
    beta: float = Field(gt=0, json_schema_extra=PUBLIC)  # dispersion


class InitialStateFile(Contract):
    """Operational state at advisory 1: per-entity flags and event-level values."""

    entities: dict[str, dict[str, bool]] = Field(json_schema_extra=INTERNAL)
    event: dict[str, int | bool | str] = Field(json_schema_extra=INTERNAL)


class PointRecord(Contract):
    x_km: float = Field(json_schema_extra=RESTRICTED)
    y_km: float = Field(json_schema_extra=RESTRICTED)


class TrackPointRecord(Contract):
    t_hours: float = Field(ge=0, json_schema_extra=PUBLIC)
    x_km: float = Field(json_schema_extra=RESTRICTED)
    y_km: float = Field(json_schema_extra=RESTRICTED)
    vmax_mph: float = Field(gt=0, json_schema_extra=PUBLIC)
    rmax_km: float = Field(gt=0, json_schema_extra=PUBLIC)


class AdvisoryRecord(Contract):
    advisory_no: int = Field(ge=1, json_schema_extra=PUBLIC)
    issued_at: datetime = Field(json_schema_extra=PUBLIC)
    hours_to_landfall: int = Field(ge=0, json_schema_extra=PUBLIC)
    track: list[TrackPointRecord] = Field(min_length=2, json_schema_extra=PUBLIC)
    # by lead time in hours
    cone_radius_km: dict[str, float] = Field(json_schema_extra=PUBLIC)
    landfall: PointRecord = Field(json_schema_extra=PUBLIC)
    peak_surge_m: float = Field(ge=0, json_schema_extra=PUBLIC)


class HistoricalStormFile(Contract):
    """A past storm's best track (history/), for the calibration back-test. `landfall_t_hours` is
    the track time of landfall."""

    name: str = Field(min_length=1, json_schema_extra=PUBLIC)
    landfall_at: datetime = Field(json_schema_extra=PUBLIC)
    landfall_t_hours: float = Field(ge=0, json_schema_extra=PUBLIC)
    track: list[TrackPointRecord] = Field(min_length=2, json_schema_extra=PUBLIC)
    landfall: PointRecord = Field(json_schema_extra=PUBLIC)
    peak_surge_m: float = Field(ge=0, json_schema_extra=PUBLIC)


class StormOutcomeRecord(Contract):
    """Whether an asset failed in the past storm."""

    asset_id: str = Field(json_schema_extra=INTERNAL)
    failed: bool = Field(json_schema_extra=INTERNAL)


class SyntheticStormFile(HistoricalStormFile):
    """A past fictional storm of the synthetic history (history/synthetic_storms.json) with
    every asset's outcome, for training the challenger model (CR-03 C2)."""

    outcomes: list[StormOutcomeRecord] = Field(min_length=1, json_schema_extra=INTERNAL)


class LineStringGeometry(Contract):
    type: Literal["LineString"] = Field(json_schema_extra=PUBLIC)
    coordinates: list[tuple[float, float]] = Field(json_schema_extra=RESTRICTED)


class PolygonGeometry(Contract):
    type: Literal["Polygon"] = Field(json_schema_extra=PUBLIC)
    coordinates: list[list[tuple[float, float]]] = Field(json_schema_extra=RESTRICTED)


class CoastlineFeature(Contract):
    type: Literal["Feature"] = Field(json_schema_extra=PUBLIC)
    properties: dict[str, str] = Field(json_schema_extra=PUBLIC)
    geometry: LineStringGeometry | PolygonGeometry = Field(
        discriminator="type", json_schema_extra=PUBLIC
    )


class CoastlineFile(Contract):
    """GeoJSON with planar km coordinates ([x_km, y_km]) instead of longitude/latitude."""

    type: Literal["FeatureCollection"] = Field(json_schema_extra=PUBLIC)
    features: list[CoastlineFeature] = Field(json_schema_extra=PUBLIC)
