"""Field tasks (CR-02 C2): the approved package items that need field work, as the field
supervisor of one district sees them, and checking and applying their reports.

The playbook says which approved items are field work, the state that completes each and the
stop-work in force at its site (`field_work`); this module never re-derives a rule. A report is
a decision like any other: the lifecycle checks it and the cycle's decision step applies it.
Done writes the completing state; Blocked writes it as not done (approval had counted the work
as done, decisions.md 2026-10-28), so the finding opens again and the next package's item
carries the note.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlmodel import Session, col, select

from app import advisory_context
from app.errors import AppError, ConflictError, NotFound
from app.models import Advisory, Asset, FieldReport, FieldStatus, OpState, PackageItem, StagingArea
from app.playbook.package import FieldWork, field_work
from app.playbook.service import Playbook, entity_names, reevaluate
from app.replay import service

FIELD_SUPERVISOR = "field_supervisor"
TaskStatus = Literal["open", "done", "blocked"]


class StopWork(ConflictError):
    code = "stop_work"


class AlreadyDone(ConflictError):
    code = "already_done"


class NoteRequired(AppError):
    status = 422
    code = "note_required"


@dataclass(frozen=True)
class FieldReportRequest:
    """A field supervisor of `district` reports a task done or blocked."""

    district: str
    outcome: FieldStatus
    note: str | None = None


@dataclass(frozen=True)
class FieldTask:
    work: FieldWork
    entity_name: str | None
    why: str  # the clause's title, one line
    report: FieldReport | None

    @property
    def status(self) -> TaskStatus:
        return self.report.status if self.report else "open"


def districts(session: Session) -> list[str]:
    """The districts of the asset data (staging areas lie in them too), by name."""
    return sorted(set(_district_of(session).values()))


def _district_of(session: Session) -> dict[str, str]:
    where = {a.id: a.district for a in session.exec(select(Asset))}
    return where | {s.id: s.district for s in session.exec(select(StagingArea))}


def current_tasks(session: Session, playbook: Playbook, district: str) -> list[FieldTask]:
    """The field tasks of `district` as they stand at the current advisory (none before the
    first)."""
    advisory_no = advisory_context.current_advisory_no(session)
    if not advisory_no:
        _require_district(_district_of(session), district)
        return []
    return tasks(session, playbook, service.require_issued(session, advisory_no), district)


def _require_district(where: dict[str, str], district: str) -> None:
    if district not in where.values():
        raise NotFound(f"no district {district!r}")


def tasks(
    session: Session, playbook: Playbook, advisory: Advisory, district: str
) -> list[FieldTask]:
    """The field tasks at sites in `district` as they stand at `advisory`, oldest first; other
    districts' tasks are never included."""
    where = _district_of(session)
    _require_district(where, district)
    names = entity_names(session)
    reports = {r.item_id: r for r in session.exec(select(FieldReport))}
    return [
        FieldTask(
            w,
            names.get(w.item.entity_id),
            playbook.rule(w.item.rule_id).title,
            reports.get(w.item.id or 0),
        )
        for w in field_work(session, advisory, playbook)
        if where.get(w.item.entity_id) == district
    ]


def check(
    session: Session,
    playbook: Playbook,
    advisory: Advisory,
    item_id: int,
    request: FieldReportRequest,
) -> FieldTask:
    """Raises unless the district's supervisor may report this outcome on this task at
    `advisory`: Done is final and refused under stop-work (P-4.7); Blocked needs a note."""
    task = next(
        (
            t
            for t in tasks(session, playbook, advisory, request.district)
            if t.work.item.id == item_id
        ),
        None,
    )
    if task is None:
        raise NotFound(f"no field task {item_id} in {request.district}")
    if task.status == "done":
        raise AlreadyDone(f"field task {item_id} was already reported done")
    if request.outcome == "done" and task.work.stop_work:
        raise StopWork(
            f"Stop work: {', '.join(task.work.stop_work)}. Tropical-storm-force wind is due "
            "within 12 hours; the task cannot be done now."
        )
    if request.outcome == "blocked" and not (request.note or "").strip():
        raise NoteRequired("A blocked task needs a note saying why.")
    return task


def apply(
    session: Session,
    playbook: Playbook,
    advisory: Advisory,
    item_id: int,
    request: FieldReportRequest,
) -> tuple[FieldTask, dict[str, object]]:
    """Records the report, writes the completing state (done) or its absence (blocked) and
    re-evaluates the item's finding at `advisory`. Returns the task and the state written."""
    task = check(session, playbook, advisory, item_id, request)
    now = datetime.now(UTC)
    done = request.outcome == "done"
    written: dict[str, object] = {}
    for change in task.work.completes:
        value = change.value if done else False
        session.merge(
            OpState(
                entity=change.entity,
                key=change.key,
                value=value,
                set_by=FIELD_SUPERVISOR,
                set_at=now,
            )
        )
        written[f"{change.entity}.{change.key}"] = value
    session.merge(
        FieldReport(
            item_id=item_id,
            advisory_no=advisory.advisory_no,
            status=request.outcome,
            note=(request.note or "").strip() or None,
            reported_at=now,
        )
    )
    session.flush()
    item = task.work.item
    reevaluate(session, advisory, playbook, item.rule_id, item.entity_id)
    return task, written


def blocked_notes(session: Session, advisory_no: int) -> dict[tuple[str, str], str]:
    """The note of each work (rule and site) whose latest report before `advisory_no` is
    Blocked: the gap a new package item for it carries."""
    reported = session.exec(
        select(FieldReport, PackageItem)
        .where(FieldReport.item_id == PackageItem.id, FieldReport.advisory_no < advisory_no)
        .order_by(col(FieldReport.reported_at))
    ).all()
    latest = {(i.rule_id, i.entity_id): r for r, i in reported}
    return {work: r.note or "" for work, r in latest.items() if r.status == "blocked"}
