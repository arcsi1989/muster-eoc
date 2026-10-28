from typing import Annotated

from fastapi import APIRouter, Query

from app.api.schemas import ExposureOut
from app.deps import SessionDep
from app.replay import service

router = APIRouter()


@router.get("/exposure", response_model=list[ExposureOut])
def get_exposure(
    session: SessionDep,
    advisory: Annotated[int, Query(ge=1)],
) -> list[ExposureOut]:
    """Hazard exposure of every asset and staging area at an issued advisory."""
    return [
        ExposureOut.model_validate(e, from_attributes=True)
        for e in service.exposures(session, advisory)
    ]
