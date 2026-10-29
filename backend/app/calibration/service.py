"""Runs the calibration (plan M8): back-tests the version in use on the past storm, fits the
curves by MAP with the published curves as the prior, back-tests the fit, and stores it as a
proposed model version that a person approves before it is used."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np
from sqlmodel import Session, select

from app import advisory_context
from app.audit.log import record
from app.calibration import versions
from app.calibration.backtest import (
    BacktestMetrics,
    BestTrack,
    Observation,
    best_track_exposure,
    evaluate,
)
from app.calibration.backtest import predict as predict_failures
from app.calibration.fit import fit_map
from app.errors import DataNotLoaded
from app.hazard.service import sites
from app.ingest.loader import PUBLISHED_VERSION
from app.models import (
    Advisory,
    Asset,
    Coastline,
    FragilityCurve,
    HistoricalStorm,
    ModelVersion,
    StormOutcome,
)
from app.scoring_config import ScoringConfig

CALIBRATION_EVENT = "calibration_run"


@dataclass(frozen=True)
class CalibrationRun:
    storm: str
    before_version: int
    before: BacktestMetrics
    after: BacktestMetrics
    proposed: ModelVersion


def observations(session: Session, config: ScoringConfig) -> list[Observation]:
    """Every asset's exposure along the storm's best track, and whether it failed."""
    storm = session.get(HistoricalStorm, config.calibration.storm)
    coastline = session.get(Coastline, 1)
    if storm is None or coastline is None:
        raise DataNotLoaded(f"{config.calibration.storm} missing; the gold data was not loaded")
    failed = {
        o.asset_id: o.failed
        for o in session.exec(select(StormOutcome).where(StormOutcome.storm == storm.name))
    }
    assets = {a.id: a for a in session.exec(select(Asset))}
    exposures = best_track_exposure(
        BestTrack(
            storm.track,
            storm.landfall_t_hours,
            (storm.landfall_x_km, storm.landfall_y_km),
            storm.peak_surge_m,
        ),
        [s for s in sites(session, config.hazard) if s.id in failed],
        [(x, y) for x, y in coastline.coastline],
        [(x, y) for x, y in coastline.land],
        config.hazard,
    )
    return [
        Observation(
            asset_id=e.site_id,
            asset_type=assets[e.site_id].type,
            condition_score=assets[e.site_id].condition_score,
            wind_mph=float(e.wind_members_mph[0]),
            flood_m=float(e.flood_members_m[0]),
            failed=failed[e.site_id],
        )
        for e in exposures
    ]


def run(session: Session, config: ScoringConfig) -> CalibrationRun:
    calibration = config.calibration
    step = config.risk.condition_theta_reduction_per_step
    observed = observations(session, config)
    failed = np.array([o.failed for o in observed])

    def backtest(curves: list[FragilityCurve]) -> BacktestMetrics:
        p = predict_failures(observed, curves, step)
        return evaluate(p, failed, calibration.reliability_bins, calibration.top_fraction)

    current = versions.in_use(session)
    published = session.get(ModelVersion, PUBLISHED_VERSION)
    if published is None:
        raise DataNotLoaded("the published model version is missing")
    fitted = fit_map(
        observed,
        versions.curves(published),
        step,
        calibration.prior_sd_log_theta,
        calibration.prior_sd_log_beta,
    )
    before, after = backtest(current.curves), backtest(fitted)
    proposed = ModelVersion(
        label=f"Calibrated on {calibration.storm}",
        status="proposed",
        curves=[
            {"asset_type": c.asset_type, "hazard": c.hazard, "theta": c.theta, "beta": c.beta}
            for c in fitted
        ],
        created_at=datetime.now(UTC),
        backtest={
            "storm": calibration.storm,
            "before_version": current.id,
            "before": asdict(before),
            "after": asdict(after),
        },
    )
    session.add(proposed)
    session.flush()
    advisory_no = advisory_context.current_advisory_no(session)
    record(
        session,
        "system",
        CALIBRATION_EVENT,
        f"Calibrated on {calibration.storm}: Brier score {before.brier:.3f} -> {after.brier:.3f}; "
        f"model version {proposed.id} proposed, awaiting approval",
        session.get(Advisory, advisory_no) if advisory_no else None,
        {
            "model_version": proposed.id,
            "before_version": current.id,
            "brier_before": before.brier,
            "brier_after": after.brier,
            "top_capture_before": before.top_capture,
            "top_capture_after": after.top_capture,
        },
        {"model_version": current.id},
    )
    session.commit()
    session.refresh(proposed)
    return CalibrationRun(calibration.storm, current.id, before, after, proposed)
