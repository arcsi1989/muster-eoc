from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.schemas import ClauseOut, FindingOut
from app.deps import PlaybookDep, SessionDep
from app.playbook.engine import Status
from app.playbook.service import finding_views
from app.replay import service

router = APIRouter()


@router.get("/clauses", response_model=list[ClauseOut])
def list_clauses(playbook: PlaybookDep) -> list[ClauseOut]:
    return [ClauseOut.model_validate(asdict(c)) for c in playbook.clauses]


@router.get("/findings", response_model=list[FindingOut])
def list_findings(
    session: SessionDep,
    playbook: PlaybookDep,
    advisory: Annotated[int, Query(ge=1)],
    status: Status | None = None,
) -> list[FindingOut]:
    """Playbook findings at an issued advisory, optionally filtered by status."""
    service.require_issued(session, advisory)
    return [
        FindingOut(
            **v.finding.model_dump(include=set(FindingOut.model_fields)),
            title=v.title,
            entity_name=v.entity_name,
        )
        for v in finding_views(session, playbook, advisory, status)
    ]
