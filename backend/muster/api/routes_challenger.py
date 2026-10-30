from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from muster.api.model_version_out import version_out
from muster.api.schemas import (
    ChallengerOut,
    DisagreementOut,
    DisagreementsOut,
    ModelMetricsOut,
    ModelVersionOut,
    PromotionCheckOut,
)
from muster.calibration import versions
from muster.challenger import promotion, shadow
from muster.challenger.model import ChallengerModel
from muster.deps import ChallengerDep, ModelsConfigDep, ScoringConfigDep, SessionDep
from muster.errors import NotFound

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


@router.get("/disagreements", response_model=DisagreementsOut)
def get_disagreements(
    session: SessionDep,
    challenger: ChallengerDep,
    models: ModelsConfigDep,
    scoring: ScoringConfigDep,
    advisory: Annotated[int, Query(ge=1)],
) -> DisagreementsOut:
    """The assets the challenger ranks in its top N at an advisory that the champion does not,
    with the challenger's top features: why it ranks them higher."""
    version = _loaded(challenger).version
    top_n = scoring.risk.top_n
    found = shadow.disagreements(
        session, advisory, version, top_n, models.challenger.explain_features
    )
    return DisagreementsOut(
        advisory_no=advisory,
        model_version=version,
        top_n=top_n,
        items=[DisagreementOut.model_validate(d, from_attributes=True) for d in found],
    )
