from fastapi import APIRouter

from muster.api.params import AdvisoryQuery
from muster.api.schemas import ExposureOut
from muster.deps import SessionDep
from muster.replay import service

router = APIRouter()


@router.get("/exposure", response_model=list[ExposureOut])
def get_exposure(
    session: SessionDep,
    advisory: AdvisoryQuery,
) -> list[ExposureOut]:
    """Hazard exposure of every asset and staging area at an issued advisory."""
    return [
        ExposureOut.model_validate(e, from_attributes=True)
        for e in service.exposures(session, advisory)
    ]
