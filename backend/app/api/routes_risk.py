from typing import Annotated

from fastapi import APIRouter, Query

from app.api.schemas import (
    AlertOut,
    AssetOut,
    DependencyLinkOut,
    ExplainOut,
    ExposureOut,
    RiskItemOut,
    RiskListOut,
)
from app.deps import SessionDep
from app.replay import service
from app.risk.explain import explain_asset

router = APIRouter()

AdvisoryQuery = Annotated[int, Query(ge=1)]


@router.get("/risk", response_model=RiskListOut)
def get_risk(session: SessionDep, advisory: AdvisoryQuery) -> RiskListOut:
    scores = service.ranked_scores(session, advisory)
    previous = service.ranks(session, advisory - 1)
    return RiskListOut(
        advisory_no=advisory,
        model_version=scores[0].model_version,
        items=[
            RiskItemOut(
                asset_id=s.asset_id,
                p_fail=s.p_fail,
                consequence=s.consequence,
                risk=s.risk,
                rank=s.rank,
                previous_rank=previous.get(s.asset_id),
                confidence=s.confidence,
            )
            for s in scores
        ],
    )


@router.get("/assets/{asset_id}/explain", response_model=ExplainOut)
def explain(asset_id: str, session: SessionDep, advisory: AdvisoryQuery) -> ExplainOut:
    """Why an asset ranks where it does: exposure, fragility, condition, consequence."""
    e = explain_asset(session, asset_id, advisory)
    return ExplainOut(
        asset=AssetOut.model_validate(e.asset, from_attributes=True),
        advisory_no=advisory,
        rank=e.score.rank,
        risk=e.score.risk,
        p_fail=e.score.p_fail,
        p_wind=e.score.p_wind,
        p_flood=e.score.p_flood,
        wind=e.factors["wind"],
        flood=e.factors["flood"],
        exposure=ExposureOut.model_validate(e.exposure, from_attributes=True),
        consequence=e.factors["consequence"],
        confidence=e.score.confidence,
        confidence_reasons=e.score.confidence_reasons,
        feeds=[DependencyLinkOut.model_validate(link, from_attributes=True) for link in e.feeds],
        fed_by=[DependencyLinkOut.model_validate(link, from_attributes=True) for link in e.fed_by],
    )


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(session: SessionDep, advisory: AdvisoryQuery) -> list[AlertOut]:
    return [
        AlertOut.model_validate(a, from_attributes=True) for a in service.alerts(session, advisory)
    ]
