"""What changed between two advisories: forecast, activation level and the ranking.

Reused by the advisory cycle's diff step (ticket 06).
"""

import math
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

COMPASS = ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"]


@dataclass(frozen=True)
class AdvisorySnapshot:
    advisory_no: int
    landfall_x_km: float
    landfall_y_km: float
    max_wind_mph: float
    peak_surge_m: float
    activation_level: str | None
    ranks: dict[str, int]


class LandfallShift(BaseModel):
    model_config = ConfigDict(frozen=True)

    distance_km: float
    direction: str


class RankMove(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    from_rank: int
    to_rank: int


class AdvisoryChanges(BaseModel):
    """What changed: one model, stored in the decision package and served by the API as is."""

    model_config = ConfigDict(frozen=True)

    advisory_no: int
    previous_advisory_no: int | None = None  # None at the first advisory: everything is initial
    landfall_shift: LandfallShift | None = None
    max_wind_change_mph: float | None = None
    peak_surge_change_m: float | None = None
    activation_level_from: str | None = None
    activation_level_to: str | None = None
    top10_entered: list[str] = Field(default_factory=list)
    top10_left: list[str] = Field(default_factory=list)
    rank_moves: list[RankMove] = Field(default_factory=list)  # biggest move first


def compass_direction(dx_km: float, dy_km: float) -> str:
    """8-point direction on the km grid, with y pointing north."""
    angle = math.degrees(math.atan2(dy_km, dx_km)) % 360
    return COMPASS[round(angle / 45) % 8]


def diff(
    current: AdvisorySnapshot, previous: AdvisorySnapshot | None, top_n: int
) -> AdvisoryChanges:
    """Changes since the previous advisory, with the top `top_n` compared. At the first advisory
    everything is initial."""
    if previous is None:
        return AdvisoryChanges(
            advisory_no=current.advisory_no, activation_level_to=current.activation_level
        )

    dx = current.landfall_x_km - previous.landfall_x_km
    dy = current.landfall_y_km - previous.landfall_y_km
    distance = round(math.hypot(dx, dy), 1)
    shift = (
        LandfallShift(distance_km=distance, direction=compass_direction(dx, dy))
        if distance > 0
        else None
    )

    def top(ranks: dict[str, int]) -> set[str]:
        return {asset_id for asset_id, rank in ranks.items() if rank <= top_n}

    moves = [
        RankMove(asset_id=asset_id, from_rank=previous.ranks[asset_id], to_rank=rank)
        for asset_id, rank in current.ranks.items()
        if asset_id in previous.ranks and previous.ranks[asset_id] != rank
    ]
    moves.sort(key=lambda m: (-abs(m.from_rank - m.to_rank), m.to_rank))

    return AdvisoryChanges(
        advisory_no=current.advisory_no,
        previous_advisory_no=previous.advisory_no,
        landfall_shift=shift,
        max_wind_change_mph=round(current.max_wind_mph - previous.max_wind_mph, 1),
        peak_surge_change_m=round(current.peak_surge_m - previous.peak_surge_m, 2),
        activation_level_from=previous.activation_level,
        activation_level_to=current.activation_level,
        top10_entered=sorted(top(current.ranks) - top(previous.ranks)),
        top10_left=sorted(top(previous.ranks) - top(current.ranks)),
        rank_moves=moves,
    )
