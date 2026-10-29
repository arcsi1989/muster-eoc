"""The back-test on a past storm (plan M8): how well a set of fragility curves predicted the
failures Storm Delta caused. Exposure comes from the storm's best track (no ensemble: the track
is known), failure probabilities from the curves, and the scores are a reliability table, the
Brier score and the share of failures among the highest predicted (top-decile capture)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.geo import FloatArray, Point
from app.hazard.ensemble import Site, SiteExposure, StormInput, compute_exposure
from app.models import FragilityCurve
from app.risk.fragility import adjusted_theta, combine, failure_probability
from app.scoring_config import HazardConfig

BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class Observation:
    """One asset during the past storm: what it was exposed to and whether it failed."""

    asset_id: str
    asset_type: str
    condition_score: int
    wind_mph: float
    flood_m: float
    failed: bool


@dataclass(frozen=True)
class BestTrack:
    """A past storm's observed track: `landfall_t_hours` is the track time of landfall."""

    track: list[dict[str, Any]]
    landfall_t_hours: float
    landfall: Point
    peak_surge_m: float


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float | None  # None for an empty bin
    observed_rate: float | None


@dataclass(frozen=True)
class BacktestMetrics:
    assets: int
    failures: int
    brier: float
    top_fraction: float  # of assets, by predicted probability (0.10: the top decile)
    top_capture: float  # share of all failures among them
    reliability: list[ReliabilityBin]


def best_track_exposure(
    storm: BestTrack,
    sites: list[Site],
    coastline: list[Point],
    land: list[Point],
    config: HazardConfig,
) -> list[SiteExposure]:
    """Wind and flood depth at each site along a known track: the ensemble hazard model with one
    member and no sideways shift."""
    one_member = config.model_copy(
        update={"ensemble": config.ensemble.model_copy(update={"members": 1})}
    )
    known = StormInput(
        advisory_no=0,
        hours_to_landfall=math.ceil(storm.landfall_t_hours),
        track=storm.track,
        cone_radius_km={"0": 0.0},  # no forecast uncertainty: the shift is always zero
        landfall=storm.landfall,
        peak_surge_m=storm.peak_surge_m,
    )
    return compute_exposure(known, sites, coastline, land, one_member)


def predict(
    observations: Sequence[Observation],
    curves: Sequence[FragilityCurve],
    reduction_per_step: float,
) -> FloatArray:
    """Failure probability per observation under the curves, with the condition adjustment, as
    the risk score computes it (plan section 3)."""
    curve = {(c.asset_type, c.hazard): c for c in curves}
    # The condition adjustment scales theta, so it is one factor per asset.
    factor = np.array(
        [adjusted_theta(1.0, o.condition_score, reduction_per_step) for o in observations]
    )
    by_hazard = []
    for hazard, intensity in (
        ("wind", np.array([o.wind_mph for o in observations])),
        ("flood", np.array([o.flood_m for o in observations])),
    ):
        used = [curve[(o.asset_type, hazard)] for o in observations]
        theta = np.array([c.theta for c in used]) * factor
        by_hazard.append(failure_probability(intensity, theta, np.array([c.beta for c in used])))
    return combine(by_hazard[0], by_hazard[1])


def brier_score(p: FloatArray, failed: BoolArray) -> float:
    return float(np.mean((p - failed.astype(float)) ** 2))


def reliability(p: FloatArray, failed: BoolArray, bins: int) -> list[ReliabilityBin]:
    """Equal-width bins over [0, 1]; a probability of exactly 1 falls in the last bin."""
    index = np.minimum((p * bins).astype(int), bins - 1)
    table = []
    for b in range(bins):
        members = index == b
        count = int(members.sum())
        table.append(
            ReliabilityBin(
                lower=round(b / bins, 6),
                upper=round((b + 1) / bins, 6),
                count=count,
                mean_predicted=float(p[members].mean()) if count else None,
                observed_rate=float(failed[members].mean()) if count else None,
            )
        )
    return table


def top_capture(p: FloatArray, failed: BoolArray, fraction: float) -> float:
    """Share of all failures among the `fraction` of assets with the highest predicted
    probability (ties broken by order); zero when nothing failed."""
    total = int(failed.sum())
    if total == 0:
        return 0.0
    top = np.argsort(-p, kind="stable")[: math.ceil(fraction * len(p))]
    return float(failed[top].sum()) / total


def evaluate(p: FloatArray, failed: BoolArray, bins: int, top_fraction: float) -> BacktestMetrics:
    return BacktestMetrics(
        assets=len(p),
        failures=int(failed.sum()),
        brier=brier_score(p, failed),
        top_fraction=top_fraction,
        top_capture=top_capture(p, failed, top_fraction),
        reliability=reliability(p, failed, bins),
    )
