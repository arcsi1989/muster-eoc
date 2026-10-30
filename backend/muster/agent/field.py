"""Field tasks (CR-02 C2): the approved package items that need field work, as the field
supervisor of one district sees them, and checking and applying their reports.

The playbook says which approved items are field work, the state that completes each and the
stop-work in force at its site (`field_work`); this module never re-derives a rule. A report is
a decision like any other: the lifecycle checks it and the cycle's decision step applies it.
Done writes the completing state; Blocked writes it as not done (approval had counted the work
as done, decisions.md 2026-10-28), so the finding opens again and the next package's item
carries the note.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

from sqlmodel import Session, col, select

from muster import advisory_context
from muster.agent.decisions import write_state
from muster.errors import AppError, ConflictError, NotFound
from muster.models import Advisory, Asset, FieldReport, FieldStatus, PackageItem, StagingArea
from muster.playbook.package import FieldWork, StateChange, field_work
from muster.playbook.service import Playbook, entity_names, reevaluate
from muster.replay import service

FIELD_SUPERVISOR: Final = "field_supervisor"  # the audit actor and the state's set_by
FIELD_REPORT = "field_report"  # the decision step's action for a report
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
    """A field supervisor of `district` reports a task done or blocked. The note is stripped;
    a blank one is None."""

    district: str
    outcome: FieldStatus
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "note", (self.note or "").strip() or None)

    def to_resume(self, item_id: int) -> dict[str, Any]:
        """The report as the cycle's decision step receives it."""
        return {"action": FIELD_REPORT, "item_id": item_id, **asdict(self)}

    @classmethod
    def from_resume(cls, decision: dict[str, Any]) -> FieldReportRequest:
        return cls(decision["district"], decision["outcome"], decision["note"])


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
    district_by_site = {a.id: a.district for a in session.exec(select(Asset))}
    return district_by_site | {s.id: s.district for s in session.exec(select(StagingArea))}


def current_tasks(session: Session, playbook: Playbook, district: str) -> list[FieldTask]:
    """The field tasks of `district` as they stand at the current advisory (none before the
    first)."""
    advisory_no = advisory_context.current_advisory_no(session)
    if not advisory_no:
        _require_district(_district_of(session), district)
        return []
    return tasks(session, playbook, service.require_issued(session, advisory_no), district)


def _require_district(district_by_site: dict[str, str], district: str) -> None:
    if district not in district_by_site.values():
        raise NotFound(f"no district {district!r}")


def tasks(
    session: Session, playbook: Playbook, advisory: Advisory, district: str
) -> list[FieldTask]:
    """The field tasks at sites in `district` as they stand at `advisory`, oldest first; other
    districts' tasks are never included."""
    district_by_site = _district_of(session)
    _require_district(district_by_site, district)
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
        if district_by_site.get(w.item.entity_id) == district
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
        in_force = "; ".join(f"{r} ({playbook.rule(r).title})" for r in task.work.stop_work)
        raise StopWork(f"Stop work: {in_force}. The task cannot be done now.")
    if request.outcome == "blocked" and not request.note:
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
    changes = [c if done else StateChange(c.entity, c.key, False) for c in task.work.completes]
    written = write_state(session, changes, FIELD_SUPERVISOR, now)
    session.merge(
        FieldReport(
            item_id=item_id,
            advisory_no=advisory.advisory_no,
            status=request.outcome,
            note=request.note,
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
