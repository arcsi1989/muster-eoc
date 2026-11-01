"""Risk per asset for one advisory: p_fail x consequence, with the factor breakdown the
explanation shows (plan section 3). The rule-based score's p_fail is the mean over ensemble
members of the fragility curves; an approved challenger may replace it as the champion."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np

from muster.geo import FloatArray
from muster.models import FragilityCurve
from muster.network import Network
from muster.risk.confidence import Confidence, confidence
from muster.risk.consequence import Consequence, consequence
from muster.risk.fragility import adjusted_theta, combine, failure_probability
from muster.risk.model import AssetFeatures, Prediction, RiskModel
from muster.scoring_config import ScoringConfig


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
    model_version: int  # the champion that gave p_fail
    model_factors: dict[str, Any] | None  # the champion's own factors, if not the rules'

    def factors(self) -> dict[str, Any]:
        """The stored breakdown: everything needed to reproduce the risk. The wind and flood
        breakdown is always the rule-based score's; a champion that is not adds its own."""
        result = {
            "wind": asdict(self.wind),
            "flood": asdict(self.flood),
            "consequence": {**asdict(self.consequence), "total": self.consequence.total},
        }
        if self.model_factors is not None:
            result["model"] = {"model_version": self.model_version, **self.model_factors}
        return result


@dataclass(frozen=True)
class RuleBreakdown:
    wind: HazardFactor
    flood: HazardFactor
    p_fail: float  # either hazard fails the asset, mean over members


class RuleBasedModel:
    """The rule-based score as a risk model: a fragility curve per asset type and hazard, its
    median capacity lowered for poor condition, averaged over the ensemble members."""

    def __init__(
        self, version: int, curves: Sequence[FragilityCurve], condition_step: float
    ) -> None:
        self._version = version
        self._curves = {(c.asset_type, c.hazard): c for c in curves}
        self._step = condition_step

    @property
    def version(self) -> int:
        return self._version

    def _hazard(self, features: AssetFeatures, name: str) -> tuple[HazardFactor, FloatArray]:
        """One hazard's curve for the asset and its failure probability per member."""
        asset = features.asset
        members = (
            features.exposure.wind_members_mph
            if name == "wind"
            else features.exposure.flood_members_m
        )
        c = self._curves[(asset.type, name)]
        theta_adj = adjusted_theta(c.theta, asset.condition_score, self._step)
        p = failure_probability(members, theta_adj, c.beta)
        return HazardFactor(c.theta, theta_adj, c.beta, float(p.mean())), p

    def breakdown(self, features: AssetFeatures) -> RuleBreakdown:
        (wind, p_wind), (flood, p_flood) = (
            self._hazard(features, "wind"),
            self._hazard(features, "flood"),
        )
        return RuleBreakdown(wind, flood, float(combine(p_wind, p_flood).mean()))

    def member_p_fail(self, assets: Sequence[AssetFeatures]) -> FloatArray:
        """Members x assets: each asset's failure probability under each ensemble member's
        hazard, before averaging (the outage forecast draws failures from them)."""
        columns = [combine(self._hazard(f, "wind")[1], self._hazard(f, "flood")[1]) for f in assets]
        result: FloatArray = np.array(columns).T
        return result

    def predict(self, assets: Sequence[AssetFeatures]) -> list[Prediction]:
        result = []
        for features in assets:
            b = self.breakdown(features)
            factors = {"wind": asdict(b.wind), "flood": asdict(b.flood)}
            result.append(Prediction(features.asset.id, b.p_fail, factors, self._version))
        return result


def score_assets(
    assets: Sequence[AssetFeatures],
    network: Network,
    rules: RuleBasedModel,
    champion: RiskModel,
    config: ScoringConfig,
    as_of: date,
) -> list[AssetScore]:
    """Scores every asset with the champion's p_fail. The wind and flood breakdown is the rules'
    whether or not they are the champion."""
    predictions = champion.predict(assets)
    scores = []
    for features, prediction in zip(assets, predictions, strict=True):
        asset = features.asset
        b = rules.breakdown(features)
        impact = consequence(asset.id, network, config.consequence_weights)
        level, reasons = confidence(
            features.exposure.elevation_imputed,
            asset.last_inspection_date,
            as_of,
            config.risk.stale_inspection_years,
            config.hazard.surge.imputation_neighbours,
        )
        scores.append(
            AssetScore(
                asset_id=asset.id,
                p_wind=b.wind.p_fail,
                p_flood=b.flood.p_fail,
                p_fail=prediction.p_fail,
                consequence=impact,
                risk=prediction.p_fail * impact.total,
                confidence=level,
                confidence_reasons=reasons,
                wind=b.wind,
                flood=b.flood,
                model_version=prediction.version,
                # the rules' own factors are the wind and flood breakdown already
                model_factors=None if prediction.version == rules.version else prediction.factors,
            )
        )
    return scores
