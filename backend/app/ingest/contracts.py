"""Data contracts for the gold files. Coordinates are planar km on the fictional territory."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AssetType = Literal["substation", "pump_station", "treatment_plant"]


class AssetRecord(BaseModel):
    id: str
    name: str
    type: AssetType
    x_km: float
    y_km: float
    customers_served: int = Field(ge=0)


class PointRecord(BaseModel):
    x_km: float
    y_km: float


class TrackPointRecord(BaseModel):
    t_hours: float
    x_km: float
    y_km: float
    vmax_mph: float = Field(gt=0)
    rmax_km: float = Field(gt=0)


class AdvisoryRecord(BaseModel):
    advisory_no: int = Field(ge=1)
    issued_at: datetime
    hours_to_landfall: int = Field(ge=0)
    track: list[TrackPointRecord]
    cone_radius_km: dict[str, float]
    landfall: PointRecord
    peak_surge_m: float = Field(ge=0)


class LineStringGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[tuple[float, float]]


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]


class CoastlineFeature(BaseModel):
    type: Literal["Feature"]
    properties: dict[str, str]
    geometry: LineStringGeometry | PolygonGeometry = Field(discriminator="type")


class CoastlineFile(BaseModel):
    """GeoJSON with planar km coordinates ([x_km, y_km]) instead of longitude/latitude."""

    type: Literal["FeatureCollection"]
    features: list[CoastlineFeature]
