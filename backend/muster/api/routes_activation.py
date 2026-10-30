from fastapi import APIRouter

from muster.agent.decisions import Declaration
from muster.agent.lifecycle import declare, package_view
from muster.api.package_out import package_out
from muster.api.schemas import DeclarationIn, PackageOut
from muster.deps import CycleDep, PlaybookDep, SessionDep

router = APIRouter(prefix="/activation")


@router.post("/declare", response_model=PackageOut)
def post_declaration(
    body: DeclarationIn, session: SessionDep, playbook: PlaybookDep, cycle: CycleDep
) -> PackageOut:
    """Declare the activation level the current package proposes (P-2.5): the Director declares
    Level 3 and 2, the Incident Commander Level 1. Refusals change nothing. Returns the package."""
    advisory_no = declare(session, cycle, Declaration(body.level, body.declared_by, body.reason))
    return package_out(package_view(session, playbook, cycle, advisory_no))
