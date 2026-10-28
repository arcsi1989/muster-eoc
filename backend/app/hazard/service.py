"""Computes and stores hazard exposure for an issued advisory."""

from sqlmodel import Session, select

from app.errors import DataNotLoaded
from app.hazard.ensemble import Site, SiteExposure, StormInput, compute_exposure, impute_elevations
from app.models import Advisory, Asset, Coastline, Exposure, StagingArea
from app.scoring_config import HazardConfig


def _sites(session: Session, config: HazardConfig) -> list[Site]:
    assets = session.exec(select(Asset)).all()
    elevations = impute_elevations(
        [(a.id, a.x_km, a.y_km, a.elevation_m) for a in assets], config.surge.imputation_neighbours
    )
    sites = [
        Site(a.id, "asset", a.x_km, a.y_km, *elevations[a.id], a.distance_to_coast_km)
        for a in assets
    ]
    sites += [
        Site(s.id, "staging_area", s.x_km, s.y_km, s.elevation_m, False, s.distance_to_coast_km)
        for s in session.exec(select(StagingArea))
    ]
    return sites


def store_exposure(
    session: Session, advisory: Advisory, config: HazardConfig
) -> list[SiteExposure]:
    """Computes the ensemble exposure of every asset and staging area to the advisory and stores
    it as P50 / P90. Returns the per-member values too: risk scoring averages over members."""
    coastline = session.get(Coastline, 1)
    if coastline is None:
        raise DataNotLoaded("coastline missing; the gold data was not loaded")
    storm = StormInput(
        advisory_no=advisory.advisory_no,
        hours_to_landfall=advisory.hours_to_landfall,
        track=advisory.track,
        cone_radius_km=advisory.cone_radius_km,
        landfall=(advisory.landfall_x_km, advisory.landfall_y_km),
        peak_surge_m=advisory.peak_surge_m,
    )
    exposures = compute_exposure(
        storm,
        _sites(session, config),
        [(x, y) for x, y in coastline.coastline],
        [(x, y) for x, y in coastline.land],
        config,
    )
    session.add_all(
        Exposure(
            site_id=e.site_id,
            advisory_no=advisory.advisory_no,
            site_kind=e.kind,
            wind_p50_mph=e.wind_p50_mph,
            wind_p90_mph=e.wind_p90_mph,
            flood_depth_p50_m=e.flood_depth_p50_m,
            flood_depth_p90_m=e.flood_depth_p90_m,
            tsforce_arrival_h=e.tsforce_arrival_h,
            elevation_imputed=e.elevation_imputed,
        )
        for e in exposures
    )
    return exposures
