from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.schemas import RiskItemOut, RiskListOut
from app.deps import get_session
from app.replay import service

router = APIRouter()


@router.get("/risk", response_model=RiskListOut)
def get_risk(
    session: Annotated[Session, Depends(get_session)],
    advisory: Annotated[int, Query(ge=1)],
) -> RiskListOut:
    scores = service.ranked_scores(session, advisory)
    previous = service.ranks(session, advisory - 1)
    return RiskListOut(
        advisory_no=advisory,
        items=[
            RiskItemOut(
                asset_id=s.asset_id,
                score=s.score,
                rank=s.rank,
                previous_rank=previous.get(s.asset_id),
            )
            for s in scores
        ],
    )
