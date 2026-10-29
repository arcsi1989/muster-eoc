"""Risk per asset for one advisory: p_fail (mean over ensemble members) x consequence, with the
factor breakdown the explanation shows (plan section 3)."""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np

from app.hazard.ensemble import SiteExposure
from app.models import FragilityCurve
from app.network import Network
from app.risk.confidence import Confidence, confidence
from app.risk.consequence import Consequence, consequence
from app.risk.fragility import adjusted_theta, combine, failure_probability
from app.scoring_config import ScoringConfig


@dataclass(frozen=True)
class HazardFactor:
    theta: float
    theta_adjusted: float
    beta: float
    p_fail: float  # mean over members for this hazard alone


@dataclass(frozen=True)
class AssetScore:
    asset_id: str
    p_wind: float
    p_flood: float
    p_fail: float
    consequence: Consequence
    risk: float
    confidence: Confidence
    confidence_reasons: list[str]
    wind: HazardFactor
    flood: HazardFactor

    def factors(self) -> dict[str, Any]:
        """The stored breakdown: everything needed to reproduce the risk."""
        return {
            "wind": asdict(self.wind),
            "flood": asdict(self.flood),
            "consequence": {**asdict(self.consequence), "total": self.consequence.total},
        }


def score_assets(
    exposures: list[SiteExposure],
    network: Network,
    curves: list[FragilityCurve],
    config: ScoringConfig,
    as_of: date,
) -> list[AssetScore]:
    curve = {(c.asset_type, c.hazard): c for c in curves}
    step = config.risk.condition_theta_reduction_per_step
    scores = []
    for exposure in exposures:
        asset = network.assets[exposure.site_id]
        hazard: dict[str, tuple[HazardFactor, np.ndarray]] = {}
        for name, members in (
            ("wind", exposure.wind_members_mph),
            ("flood", exposure.flood_members_m),
        ):
            c = curve[(asset.type, name)]
            theta_adj = adjusted_theta(c.theta, asset.condition_score, step)
            p = failure_probability(members, theta_adj, c.beta)
            hazard[name] = (HazardFactor(c.theta, theta_adj, c.beta, float(p.mean())), p)
        p_fail = float(combine(hazard["wind"][1], hazard["flood"][1]).mean())
        impact = consequence(asset.id, network, config.consequence_weights)
        level, reasons = confidence(
            exposure.elevation_imputed,
            asset.last_inspection_date,
            as_of,
            config.risk.stale_inspection_years,
            config.hazard.surge.imputation_neighbours,
        )
        scores.append(
            AssetScore(
                asset_id=asset.id,
                p_wind=hazard["wind"][0].p_fail,
                p_flood=hazard["flood"][0].p_fail,
                p_fail=p_fail,
                consequence=impact,
                risk=p_fail * impact.total,
                confidence=level,
                confidence_reasons=reasons,
                wind=hazard["wind"][0],
                flood=hazard["flood"][0],
            )
        )
    return scores
