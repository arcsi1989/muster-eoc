from dataclasses import asdict

from fastapi import APIRouter

from muster.api.model_version_out import version_out
from muster.api.schemas import (
    BacktestOut,
    CalibrationOut,
    ModelVersionApproveIn,
    ModelVersionOut,
)
from muster.calibration import service, versions
from muster.calibration.backtest import BacktestMetrics
from muster.deps import ScoringConfigDep, SessionDep

router = APIRouter()


def _backtest_out(model_version: int, metrics: BacktestMetrics) -> BacktestOut:
    return BacktestOut.model_validate({"model_version": model_version, **asdict(metrics)})


@router.post("/calibration/run", response_model=CalibrationOut)
def run_calibration(session: SessionDep, config: ScoringConfigDep) -> CalibrationOut:
    """Back-tests the version in use on Storm Delta, fits the curves by MAP and back-tests the
    fit. The fit is stored as a proposed model version: it scores nothing until approved."""
    result = service.run(session, config)
    proposed = version_out(session, result.proposed)
    return CalibrationOut(
        storm=result.storm,
        before=_backtest_out(result.before_version, result.before),
        after=_backtest_out(proposed.id, result.after),
        model_version=proposed,
    )


@router.get("/model-versions", response_model=list[ModelVersionOut])
def list_model_versions(session: SessionDep) -> list[ModelVersionOut]:
    return [version_out(session, v) for v in versions.all_versions(session)]


@router.post("/model-versions/{version_id}/approve", response_model=ModelVersionOut)
def approve_model_version(
    version_id: int, body: ModelVersionApproveIn, session: SessionDep
) -> ModelVersionOut:
    """A person approves a proposed model version (Planning, the Director or the Incident
    Commander); the next advisory is scored with it. Audited with who approved."""
    return version_out(session, versions.approve(session, version_id, body.role))
