"""SQLite tables (SQLModel). The schema grows per ticket; see the plan, section 2.3."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Asset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    x_km: float
    y_km: float
    customers_served: int


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


class Score(SQLModel, table=True):
    """Placeholder score per asset and advisory, replaced by the risk score in ticket 04."""

    asset_id: str = Field(primary_key=True, foreign_key="asset.id")
    advisory_no: int = Field(primary_key=True, foreign_key="advisory.advisory_no")
    score: float
    rank: int
