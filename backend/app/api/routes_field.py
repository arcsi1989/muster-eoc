"""The field supervisor's view (CR-02 C2): one district's field tasks, marked done or blocked.
A supervisor reads only their district's tasks and changes only their status."""

from fastapi import APIRouter

from app.agent import field
from app.agent.lifecycle import report_field_work
from app.api.schemas import FieldReportIn, FieldTaskOut
from app.deps import CycleDep, PlaybookDep, SessionDep
from app.models import FieldStatus

router = APIRouter(prefix="/field")


@router.get("/districts", response_model=list[str])
def list_districts(session: SessionDep) -> list[str]:
    return field.districts(session)


@router.get("/tasks", response_model=list[FieldTaskOut])
def list_tasks(district: str, session: SessionDep, playbook: PlaybookDep) -> list[FieldTaskOut]:
    """The district's approved items that need field work, at the current advisory."""
    return _out(field.current_tasks(session, playbook, district))


@router.post("/tasks/{item_id}/done", response_model=list[FieldTaskOut])
def post_done(
    item_id: int, body: FieldReportIn, session: SessionDep, playbook: PlaybookDep, cycle: CycleDep
) -> list[FieldTaskOut]:
    """Done writes the state that completes the task; refused under stop-work (P-4.7)."""
    return _report(item_id, "done", body, session, playbook, cycle)


@router.post("/tasks/{item_id}/blocked", response_model=list[FieldTaskOut])
def post_blocked(
    item_id: int, body: FieldReportIn, session: SessionDep, playbook: PlaybookDep, cycle: CycleDep
) -> list[FieldTaskOut]:
    """Blocked needs a note; the work's finding opens again and the next package shows it."""
    return _report(item_id, "blocked", body, session, playbook, cycle)


def _report(
    item_id: int,
    outcome: FieldStatus,
    body: FieldReportIn,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
) -> list[FieldTaskOut]:
    request = field.FieldReportRequest(body.district, outcome, body.note)
    report_field_work(session, playbook, cycle, item_id, request)
    return _out(field.current_tasks(session, playbook, body.district))


def _out(tasks: list[field.FieldTask]) -> list[FieldTaskOut]:
    return [
        FieldTaskOut(
            item_id=t.work.item.id or 0,
            approved_in=t.work.item.advisory_no,
            rule_id=t.work.item.rule_id,
            why=t.why,
            action=t.work.item.proposed_action,
            entity_id=t.work.item.entity_id,
            entity_name=t.entity_name,
            approved_by=t.work.item.decided_by,
            approved_at=t.work.item.decided_at,
            stop_work=t.work.stop_work,
            status=t.status,
            note=t.report.note if t.report else None,
            reported_at=t.report.reported_at if t.report else None,
        )
        for t in tasks
    ]
