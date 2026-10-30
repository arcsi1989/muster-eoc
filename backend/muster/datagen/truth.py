"""The hidden truth of the synthetic world: how past storms really failed assets. Failures are
drawn from the true fragility curves (never written to gold) and, in the synthetic history, one
effect the rule-based score does not model (`AgeConditionEffect`). Storm Delta's failures predate
the effect (docs/decisions.md): the calibration and the demo seeds rest on them."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from muster.calibration.backtest import BestTrack, Observation, best_track_exposure, predict
from muster.geo import FloatArray
from muster.hazard.ensemble import Site, impute_elevations
from muster.models import FragilityCurve
from muster.models_config import AgeConditionEffect
from muster.scoring_config import ScoringConfig


@dataclass(frozen=True)
class HiddenTruth:
    """How past storms really failed assets: the true curves and, if any, the age x condition
    effect, with asset ages counted to `year`."""

    curves: list[FragilityCurve]
    effect: AgeConditionEffect | None
    year: int


def extra_failure_probability(
    asset: dict[str, Any], wind_mph: float, flood_m: float, effect: AgeConditionEffect, year: int
) -> float:
    """What the age x condition effect adds: nothing unless the asset is old, in poor condition
    and under strong wind; more when flood comes with the wind."""
    if (
        year - asset["install_year"] <= effect.min_age_years
        or asset["condition_score"] < effect.min_condition_score
        or wind_mph < effect.min_wind_mph
    ):
        return 0.0
    if flood_m >= effect.min_flood_m:
        return effect.extra_failure_probability_flooded
    return effect.extra_failure_probability


def true_failure_probability(
    observations: list[Observation],
    assets: dict[str, dict[str, Any]],
    truth: HiddenTruth,
    reduction_per_step: float,
) -> FloatArray:
    """The true curves with the condition adjustment, then the age x condition effect if any."""
    p = predict(observations, truth.curves, reduction_per_step)
    effect = truth.effect
    if effect is None:
        return p
    extra = np.array(
        [
            extra_failure_probability(assets[o.asset_id], o.wind_mph, o.flood_m, effect, truth.year)
            for o in observations
        ]
    )
    result: FloatArray = 1 - (1 - p) * (1 - extra)
    return result


def simulate_failures(
    storm: dict[str, Any],
    assets: list[dict[str, Any]],
    coastline: dict[str, Any],
    truth: HiddenTruth,
    config: ScoringConfig,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Which assets failed in a past storm (a historical storm file's fields, gold asset rows and
    coastline as the generator writes them): drawn from the true failure probability under the
    exposure the back-test computes from the best track."""
    elevations = impute_elevations(
        [(a["id"], a["x_km"], a["y_km"], a["elevation_m"]) for a in assets],
        config.hazard.surge.imputation_neighbours,
    )
    sites = [
        Site(
            a["id"], "asset", a["x_km"], a["y_km"], *elevations[a["id"]], a["distance_to_coast_km"]
        )
        for a in assets
    ]
    line, land = (f["geometry"]["coordinates"] for f in coastline["features"])
    exposures = best_track_exposure(
        BestTrack(
            storm["track"],
            storm["landfall_t_hours"],
            (storm["landfall"]["x_km"], storm["landfall"]["y_km"]),
            storm["peak_surge_m"],
        ),
        sites,
        [tuple(p) for p in line],
        [tuple(p) for p in land[0]],
        config.hazard,
    )
    by_id = {a["id"]: a for a in assets}
    observations = [
        Observation(
            e.site_id,
            by_id[e.site_id]["type"],
            by_id[e.site_id]["condition_score"],
            float(e.wind_members_mph[0]),
            float(e.flood_members_m[0]),
            False,
        )
        for e in exposures
    ]
    p_true = true_failure_probability(
        observations,
        by_id,
        truth,
        config.risk.condition_theta_reduction_per_step,
    )
    draws = rng.random(len(observations))
    return [
        {"asset_id": o.asset_id, "failed": bool(u < p)}
        for o, u, p in sorted(
            zip(observations, draws, p_true, strict=True), key=lambda t: t[0].asset_id
        )
    ]
