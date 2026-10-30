from dataclasses import asdict

from fastapi import APIRouter
from sqlmodel import Session

from app.api.routes_calibration import version_out
from app.api.schemas import ChallengerOut, ModelMetricsOut, ModelVersionOut, PromotionCheckOut
from app.challenger import promotion
from app.challenger.model import ChallengerModel
from app.deps import ChallengerDep, ModelsConfigDep, SessionDep
from app.errors import NotFound
from app.models import ModelVersion

router = APIRouter(prefix="/challenger")


def _loaded(challenger: ChallengerModel | None) -> ChallengerModel:
    if challenger is None:
        raise NotFound("no challenger model is loaded; run make train")
    return challenger


def _version(session: Session, challenger: ChallengerModel) -> ModelVersion:
    version = session.get(ModelVersion, challenger.version)
    if version is None:
        raise NotFound(f"model version {challenger.version} does not exist")
    return version


@router.get("", response_model=ChallengerOut)
def get_challenger(
    session: SessionDep, challenger: ChallengerDep, config: ModelsConfigDep
) -> ChallengerOut:
    """The challenger's model version, both models' metrics on the held-out storm and whether
    the promotion rule lets it be proposed."""
    loaded = _loaded(challenger)
    trained = loaded.trained
    check = promotion.check(trained.held_out_storm, trained.held_out, config.promotion)
    return ChallengerOut(
        model_version=version_out(session, _version(session, loaded)),
        challenger=ModelMetricsOut.model_validate(asdict(trained.held_out.challenger)),
        champion=ModelMetricsOut.model_validate(asdict(trained.held_out.champion)),
        promotion=PromotionCheckOut.model_validate({**asdict(check), "passed": check.passed}),
    )


@router.post("/propose", response_model=ModelVersionOut)
def propose_challenger(
    session: SessionDep, challenger: ChallengerDep, config: ModelsConfigDep
) -> ModelVersionOut:
    """Proposes the challenger for approval if it passes the promotion rule (409 otherwise).
    It ranks nothing until a person approves it at POST /model-versions/{id}/approve."""
    version = promotion.propose(session, _loaded(challenger), config.promotion)
    return version_out(session, version)
