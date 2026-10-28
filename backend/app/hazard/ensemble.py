"""Hazard exposure per site for one advisory: a 50-member ensemble of sideways-shifted tracks
(plan section 3), summarised as P50 / P90 and the arrival of tropical-storm-force wind."""

import statistics
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from app.geo import FloatArray, Point, inside_polygon, project_onto_polyline
from app.hazard.surge import flood_depth, local_surge
from app.hazard.track import cone_radius, heading, interpolate
from app.hazard.wind import rankine_wind
from app.scoring_config import HazardConfig

SiteKind = Literal["asset", "staging_area"]  # also used by the API schema


@dataclass(frozen=True)
class Site:
    id: str
    kind: SiteKind
    x_km: float
    y_km: float
    elevation_m: float
    elevation_imputed: bool
    distance_to_coast_km: float


@dataclass(frozen=True)
class StormInput:
    advisory_no: int
    hours_to_landfall: int
    track: list[dict[str, Any]]
    cone_radius_km: dict[str, float]
    landfall: Point
    peak_surge_m: float


@dataclass(frozen=True)
class SiteExposure:
    site_id: str
    kind: SiteKind
    wind_members_mph: FloatArray  # one value per ensemble member (p_fail averages over them)
    flood_members_m: FloatArray
    wind_p50_mph: float
    wind_p90_mph: float
    flood_depth_p50_m: float
    flood_depth_p90_m: float
    tsforce_arrival_h: float | None  # median hours from issue until wind >= 39 mph; None if never
    elevation_imputed: bool


def impute_elevations(
    sites: list[tuple[str, float, float, float | None]], neighbours: int
) -> dict[str, tuple[float, bool]]:
    """(id, x, y, elevation or None) -> (elevation, imputed). A missing elevation becomes the
    median of the nearest sites that have one."""
    known = [(sid, x, y, e) for sid, x, y, e in sites if e is not None]
    result: dict[str, tuple[float, bool]] = {}
    for sid, x, y, elevation in sites:
        if elevation is not None:
            result[sid] = (elevation, False)
            continue
        nearest = sorted(known, key=lambda k: (np.hypot(k[1] - x, k[2] - y), k[0]))[:neighbours]
        result[sid] = (float(statistics.median(k[3] for k in nearest)), True)
    return result


def compute_exposure(
    storm: StormInput,
    sites: list[Site],
    coastline: list[Point],
    land: list[Point],
    config: HazardConfig,
) -> list[SiteExposure]:
    wind_cfg, surge_cfg, ens_cfg = config.wind, config.surge, config.ensemble
    hourly = interpolate(storm.track, config.interpolation_step_hours)
    hx, hy = heading(storm.track)
    normal = np.array([-hy, hx])
    sigma = ens_cfg.sigma_cone_factor * cone_radius(storm.hours_to_landfall, storm.cone_radius_km)
    rng = np.random.default_rng(ens_cfg.seed + storm.advisory_no)
    shifts = rng.normal(0.0, sigma, ens_cfg.members)

    xy = np.array([[s.x_km, s.y_km] for s in sites])
    elevation = np.array([s.elevation_m for s in sites])
    site_coast_distance = np.array([s.distance_to_coast_km for s in sites])
    _, site_arclength = project_onto_polyline(xy, coastline)
    rmax_at_landfall = float(np.interp(storm.hours_to_landfall, hourly.t_hours, hourly.rmax_km))

    winds, floods, arrivals = [], [], []
    for shift in shifts:
        centre = hourly.xy + shift * normal
        centre_coast_distance, _ = project_onto_polyline(centre, coastline)
        far_inland = inside_polygon(centre, land) & (
            centre_coast_distance > wind_cfg.inland_decay_km
        )
        vmax = hourly.vmax_mph * np.where(far_inland, wind_cfg.inland_decay_factor, 1.0)
        r = np.hypot(*(xy[:, None, :] - centre[None, :, :]).transpose(2, 0, 1))  # sites x hours
        wind = rankine_wind(r, vmax[None, :], hourly.rmax_km[None, :], wind_cfg.alpha)
        winds.append(wind.max(axis=1))
        reached = wind >= wind_cfg.tropical_storm_force_mph
        arrivals.append(
            np.where(reached.any(axis=1), hourly.t_hours[reached.argmax(axis=1)], np.inf)
        )

        landfall = np.array([storm.landfall]) + shift * normal
        _, landfall_arclength = project_onto_polyline(landfall, coastline)
        surge = local_surge(
            storm.peak_surge_m,
            site_arclength - landfall_arclength[0],
            site_coast_distance,
            rmax_at_landfall,
            surge_cfg.decay_inland_km,
        )
        floods.append(flood_depth(surge, elevation))

    wind_members, flood_members = np.array(winds), np.array(floods)  # members x sites
    arrival_median = np.median(np.array(arrivals), axis=0)
    w50, w90 = np.percentile(wind_members, [50, 90], axis=0)
    f50, f90 = np.percentile(flood_members, [50, 90], axis=0)
    return [
        SiteExposure(
            site_id=site.id,
            kind=site.kind,
            wind_members_mph=wind_members[:, i],
            flood_members_m=flood_members[:, i],
            wind_p50_mph=round(float(w50[i]), 1),
            wind_p90_mph=round(float(w90[i]), 1),
            flood_depth_p50_m=round(float(f50[i]), 2),
            flood_depth_p90_m=round(float(f90[i]), 2),
            tsforce_arrival_h=None if np.isinf(arrival_median[i]) else float(arrival_median[i]),
            elevation_imputed=site.elevation_imputed,
        )
        for i, site in enumerate(sites)
    ]
