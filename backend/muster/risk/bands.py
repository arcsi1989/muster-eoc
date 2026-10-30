"""How the storm map colours an asset: its risk band, and the hazard that drives its p_fail."""

from typing import Literal

from muster.scoring_config import RiskBand

TopFactor = Literal["wind", "flood"]


def risk_band(p_fail: float, band_min_p_fail: dict[RiskBand, float]) -> RiskBand:
    """The highest band whose lowest failure probability `p_fail` reaches (thresholds from
    config)."""
    reached = [(p, name) for name, p in band_min_p_fail.items() if p_fail >= p]
    return max(reached)[1]


def top_factor(p_wind: float, p_flood: float) -> TopFactor:
    """The hazard with the higher failure probability on its own; wind on a tie."""
    return "wind" if p_wind >= p_flood else "flood"
