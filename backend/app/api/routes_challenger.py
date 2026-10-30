from dataclasses import asdict

from fastapi import APIRouter

from app.api.model_version_out import version_out
from app.api.schemas import ChallengerOut, ModelMetricsOut, ModelVersionOut, PromotionCheckOut
from app.calibration import versions
from app.challenger import promotion
from app.challenger.model import ChallengerModel
from app.deps import ChallengerDep, ModelsConfigDep, SessionDep
from app.errors import NotFound

router = APIRouter(prefix="/challenger")


def _loaded(challenger: ChallengerModel | None) -> ChallengerModel:
    if challenger is None:
        raise NotFound("no challenger model is loaded; run make train")
    return challenger


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
        model_version=version_out(session, versions.get(session, loaded.version)),
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
