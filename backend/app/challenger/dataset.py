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

from app.calibration import versions
from app.calibration.backtest import BestTrack, BoolArray
from app.errors import DataNotLoaded
from app.geo import FloatArray
from app.hazard.ensemble import Site, StormInput, compute_exposure
from app.hazard.service import sites
from app.ingest.contracts import AssetType, SyntheticStormFile
from app.ingest.loader import PUBLISHED_VERSION
from app.models import (
    Advisory,
    Coastline,
    FragilityCurve,
    HistoricalStorm,
    ModelVersion,
    StormOutcome,
)
from app.models_config import ChallengerConfig
from app.network import Network, load_network
from app.risk.score import score_assets
from app.scoring_config import ScoringConfig

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


def storm_sample(
    storm: PastStorm,
    seed_index: int,
    world: World,
    scoring: ScoringConfig,
    config: ChallengerConfig,
) -> StormSample:
    """The storm's rows. Exposure is the ensemble around the best track, spread as a forecast
    `forecast_cone_radius_km` wide (the ensemble seed is the scenario's plus `seed_index`)."""
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
    champion = score_assets(
        exposures, world.network, world.champion_curves, scoring, storm.landfall_at
    )
    coast_km = {s.id: s.distance_to_coast_km for s in world.sites}
    rows = []
    for e in exposures:
        asset = world.network.assets[e.site_id]
        rows.append(
            [
                e.wind_p50_mph,
                e.wind_p90_mph,
                e.flood_depth_p50_m,
                e.flood_depth_p90_m,
                asset.condition_score,
                world.age_year - asset.install_year,
                ASSET_TYPES.index(asset.type),
                float(e.elevation_imputed),
                coast_km[e.site_id],
                float(bool(world.network.feeds_facility_types(asset.id))),
            ]
        )
    return StormSample(
        storm=storm.name,
        asset_ids=[e.site_id for e in exposures],
        features=np.array(rows, dtype=float),
        failed=np.array([storm.failed[e.site_id] for e in exposures]),
        champion_p=np.array([s.p_fail for s in champion]),
    )


def stack(samples: Sequence[StormSample]) -> tuple[FloatArray, BoolArray, FloatArray, list[str]]:
    """All rows of the samples: features, outcomes, champion probabilities and each row's storm."""
    return (
        np.vstack([s.features for s in samples]),
        np.concatenate([s.failed for s in samples]),
        np.concatenate([s.champion_p for s in samples]),
        [s.storm for s in samples for _ in s.asset_ids],
    )
