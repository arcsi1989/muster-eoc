from fastapi import APIRouter

from app.agent.decisions import DecisionRequest
from app.agent.package import decide, package_view
from app.api.package_out import package_out
from app.api.schemas import DecisionIn, PackageOut
from app.deps import CycleDep, PlaybookDep, SessionDep

router = APIRouter(prefix="/packages")


@router.get("/{advisory_no}", response_model=PackageOut)
def get_package(advisory_no: int, session: SessionDep, playbook: PlaybookDep) -> PackageOut:
    return package_out(package_view(session, playbook, advisory_no))


@router.post("/{advisory_no}/items/{item_id}/decision", response_model=PackageOut)
def post_decision(
    advisory_no: int,
    item_id: int,
    body: DecisionIn,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
) -> PackageOut:
    """Approve or override a gap's action, or decide a conflict. Refusals change nothing."""
    decide(
        session,
        playbook,
        cycle,
        advisory_no,
        item_id,
        DecisionRequest(body.role, body.action, body.reason),
    )
    return package_out(package_view(session, playbook, advisory_no))
