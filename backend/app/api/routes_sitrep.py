from fastapi import APIRouter

from app.agent.lifecycle import approve_sitrep
from app.api.schemas import SitrepApproveIn, SitrepOut
from app.deps import CycleDep, PlaybookDep, SessionDep

router = APIRouter(prefix="/sitrep")


@router.post("/{advisory_no}/approve", response_model=SitrepOut)
def approve(
    advisory_no: int,
    body: SitrepApproveIn,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
) -> SitrepOut:
    """The commanding role approves the (possibly edited) draft while the package is open; P-7.1
    is then satisfied."""
    sitrep = approve_sitrep(session, playbook, cycle, advisory_no, body.role, body.text)
    return SitrepOut.model_validate(sitrep, from_attributes=True)
