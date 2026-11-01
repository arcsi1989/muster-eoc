from dataclasses import asdict

from fastapi import APIRouter

from muster import advisory_context
from muster.api.params import AdvisoryQuery
from muster.api.schemas import ClauseOut, FindingOut
from muster.deps import PlaybookDep, SessionDep
from muster.playbook.engine import Status
from muster.playbook.service import finding_views

router = APIRouter()


@router.get("/clauses", response_model=list[ClauseOut])
def list_clauses(playbook: PlaybookDep) -> list[ClauseOut]:
    return [ClauseOut.model_validate(asdict(c)) for c in playbook.clauses]


@router.get("/findings", response_model=list[FindingOut])
def list_findings(
    session: SessionDep,
    playbook: PlaybookDep,
    advisory: AdvisoryQuery,
    status: Status | None = None,
) -> list[FindingOut]:
    """Playbook findings at an issued advisory, optionally filtered by status."""
    advisory_context.require_issued(session, advisory)
    return [
        FindingOut(
            **v.finding.model_dump(include=set(FindingOut.model_fields)),
            title=v.title,
            entity_name=v.entity_name,
        )
        for v in finding_views(session, playbook, advisory, status)
    ]
