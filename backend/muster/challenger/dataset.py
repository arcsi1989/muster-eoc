"""Features and outcomes per asset and past storm. The features are what the app knows before a
storm: the ensemble's wind and flood P50/P90 around the forecast track and the asset's own
attributes. The outcome is what the storm did. The champion's prediction is the rule-based
score's failure probability on the same ensemble."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import get_args

import numpy as np
from sqlmodel import Session, func, select

from muster.calibration import versions
from muster.calibration.backtest import BestTrack, BoolArray
from muster.errors import DataNotLoaded
from muster.geo import FloatArray
from muster.hazard.ensemble import Site, StormInput, compute_exposure
from muster.hazard.service import sites
from muster.ingest.contracts import AssetType, SyntheticStormFile
from muster.ingest.loader import PUBLISHED_VERSION
from muster.models import (
    Advisory,
    Coastline,
    FragilityCurve,
    HistoricalStorm,
    ModelVersion,
    StormOutcome,
)
from muster.models_config import ChallengerConfig
from muster.network import Network, load_network
from muster.risk.model import AssetFeatures, asset_features
from muster.risk.score import RuleBasedModel
from muster.scoring_config import ScoringConfig

FEATURES = (
    "wind_p50_mph",
    "wind_p90_mph",
    "flood_p50_m",
    "flood_p90_m",
    "condition_score",
    "age_years",
    "asset_type",
    "elevation_imputed",
    "distance_to_coast_km",
    "critical_dependency",
)
ASSET_TYPES: tuple[str, ...] = get_args(AssetType)  # asset_type's category codes, in order
CATEGORICAL = (FEATURES.index("asset_type"),)


@dataclass(frozen=True)
class PastStorm:
    """A past storm's best track and which assets it failed."""

    name: str
    landfall_at: date
    best_track: BestTrack
    failed: dict[str, bool]  # asset id -> failed


@dataclass(frozen=True)
class StormSample:
    """One storm's rows: a feature matrix (assets x FEATURES), the outcomes and the champion's
    failure probabilities, in the order of `asset_ids`."""

    storm: str
    asset_ids: list[str]
    features: FloatArray
    failed: BoolArray
    champion_p: FloatArray


@dataclass(frozen=True)
class World:
    """What every storm's features are computed over: today's assets and network."""

    network: Network
    sites: list[Site]
    coastline: list[tuple[float, float]]
    land: list[tuple[float, float]]
    # The published curves, whatever version is in use: curves calibrated on the held-out storm
    # would score it in-sample.
    champion_curves: list[FragilityCurve]
    age_year: int  # the scenario's year: asset ages are counted to it


def load_world(session: Session, scoring: ScoringConfig) -> World:
    coastline = session.get(Coastline, 1)
    first_issued = session.exec(select(func.min(Advisory.issued_at))).one()
    published = session.get(ModelVersion, PUBLISHED_VERSION)
    if coastline is None or first_issued is None or published is None:
        raise DataNotLoaded("coastline, advisories or curves missing; the gold data was not loaded")
    return World(
        network=load_network(session),
        sites=[s for s in sites(session, scoring.hazard) if s.kind == "asset"],
        coastline=[(x, y) for x, y in coastline.coastline],
        land=[(x, y) for x, y in coastline.land],
        champion_curves=versions.curves(published),
        age_year=first_issued.year,
    )


def held_out_storm(session: Session, name: str) -> PastStorm:
    """The held-out storm from the gold history (the calibration back-test's storm)."""
    storm = session.get(HistoricalStorm, name)
    if storm is None:
        raise DataNotLoaded(f"{name} missing; the gold data was not loaded")
    outcomes = session.exec(select(StormOutcome).where(StormOutcome.storm == name))
    return PastStorm(
        name=storm.name,
        landfall_at=storm.landfall_at.date(),
        best_track=BestTrack(
            storm.track,
            storm.landfall_t_hours,
            (storm.landfall_x_km, storm.landfall_y_km),
            storm.peak_surge_m,
        ),
        failed={o.asset_id: o.failed for o in outcomes},
    )


def training_storms(history: Sequence[SyntheticStormFile], held_out_name: str) -> list[PastStorm]:
    """The history's storms, refusing a history that contains the held-out storm."""
    storms = history_storms(history)
    if any(s.name == held_out_name for s in storms):
        raise ValueError(f"{held_out_name} is the held-out storm; it cannot be in the history")
    return storms


def history_storms(history: Sequence[SyntheticStormFile]) -> list[PastStorm]:
    return [
        PastStorm(
            name=s.name,
            landfall_at=s.landfall_at.date(),
            best_track=BestTrack(
                [p.model_dump() for p in s.track],
                s.landfall_t_hours,
                (s.landfall.x_km, s.landfall.y_km),
                s.peak_surge_m,
            ),
            failed={o.asset_id: o.failed for o in s.outcomes},
        )
        for s in history
    ]


def storm_assets(
    storm: PastStorm,
    seed_index: int,
    world: World,
    scoring: ScoringConfig,
    config: ChallengerConfig,
) -> list[AssetFeatures]:
    """The features of every asset with an outcome in the storm. Exposure is the ensemble around
    the best track, spread as a forecast `forecast_cone_radius_km` wide (the ensemble seed is
    the scenario's plus `seed_index`)."""
    best = storm.best_track
    lead_hours = math.ceil(best.landfall_t_hours)
    forecast = StormInput(
        advisory_no=seed_index,
        hours_to_landfall=lead_hours,
        track=best.track,
        cone_radius_km={str(lead_hours): config.forecast_cone_radius_km},
        landfall=best.landfall,
        peak_surge_m=best.peak_surge_m,
    )
    exposures = [
        e
        for e in compute_exposure(
            forecast, world.sites, world.coastline, world.land, scoring.hazard
        )
        if e.site_id in storm.failed
    ]
    return asset_features(exposures, world.network, world.age_year)


def published_rules(world: World, scoring: ScoringConfig) -> RuleBasedModel:
    """The rule-based score with the published curves: the champion every past storm is
    compared with."""
    return RuleBasedModel(
        PUBLISHED_VERSION, world.champion_curves, scoring.risk.condition_theta_reduction_per_step
    )


def storm_sample(
    storm: PastStorm,
    seed_index: int,
    world: World,
    scoring: ScoringConfig,
    config: ChallengerConfig,
) -> StormSample:
    """The storm's rows (see `storm_assets` for the exposure)."""
    assets = storm_assets(storm, seed_index, world, scoring, config)
    return StormSample(
        storm=storm.name,
        asset_ids=[a.asset.id for a in assets],
        features=feature_matrix(assets),
        failed=np.array([storm.failed[a.asset.id] for a in assets]),
        champion_p=np.array([p.p_fail for p in published_rules(world, scoring).predict(assets)]),
    )


def feature_matrix(assets: Sequence[AssetFeatures]) -> FloatArray:
    """One row per asset, the columns in the order of FEATURES."""
    return np.array(
        [
            [
                a.exposure.wind_p50_mph,
                a.exposure.wind_p90_mph,
                a.exposure.flood_depth_p50_m,
                a.exposure.flood_depth_p90_m,
                a.asset.condition_score,
                a.age_years,
                ASSET_TYPES.index(a.asset.type),
                float(a.exposure.elevation_imputed),
                a.asset.distance_to_coast_km,
                float(a.critical_dependency),
            ]
            for a in assets
        ],
        dtype=float,
    ).reshape(len(assets), len(FEATURES))


def stack(samples: Sequence[StormSample]) -> tuple[FloatArray, BoolArray, FloatArray, list[str]]:
    """All rows of the samples: features, outcomes, champion probabilities and each row's storm."""
    return (
        np.vstack([s.features for s in samples]),
        np.concatenate([s.failed for s in samples]),
        np.concatenate([s.champion_p for s in samples]),
        [s.storm for s in samples for _ in s.asset_ids],
    )
