from dataclasses import asdict

from fastapi import APIRouter
from sqlmodel import Session

from app.api.schemas import (
    BacktestOut,
    CalibrationOut,
    CurveOut,
    ModelVersionApproveIn,
    ModelVersionOut,
)
from app.calibration import service, versions
from app.calibration.backtest import BacktestMetrics
from app.deps import ScoringConfigDep, SessionDep
from app.models import ModelVersion

router = APIRouter()


def version_out(session: Session, version: ModelVersion) -> ModelVersionOut:
    return ModelVersionOut(
        id=version.id or 0,
        label=version.label,
        kind=version.kind,
        status=version.status,
        in_use=version.id == versions.champion(session).id,
        curves=[CurveOut.model_validate(c) for c in version.curves],
        created_at=version.created_at,
        approved_by=version.approved_by,
        approved_at=version.approved_at,
    )


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
