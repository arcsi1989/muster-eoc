"""The decision package lifecycle through a seeded session, without HTTP: one answer to "is the
package open", and the path every item decision takes."""

from typing import Any, cast

import pytest
from sqlmodel import col, select

from app.agent import lifecycle
from app.agent.decisions import AlreadyDecided, DecisionRefused, DecisionRequest, Declaration
from app.models import AuditEvent, DecisionPackage, OpState, PackageItem
from app.playbook.activation import Level
from tests.conftest import SeededScenario


def item(seeded: SeededScenario, advisory_no: int, rule_id: str) -> PackageItem:
    view = lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, advisory_no)
    return next(v.item for v in view.items if v.item.rule_id == rule_id)


def decide(seeded: SeededScenario, advisory_no: int, target: PackageItem, *request: Any) -> None:
    lifecycle.decide(
        seeded.session,
        seeded.playbook,
        seeded.cycle,
        advisory_no,
        target.id or 0,
        DecisionRequest(*request),
    )


def snapshot(seeded: SeededScenario) -> tuple[Any, ...]:
    """Everything a decision may change: items, operational state, the audit log."""
    seeded.session.expire_all()
    items = [i.model_dump() for i in seeded.session.exec(select(PackageItem))]
    state = [s.model_dump() for s in seeded.session.exec(select(OpState))]
    events = [e.id for e in seeded.session.exec(select(AuditEvent))]
    return items, state, events


def served_status(seeded: SeededScenario, advisory_no: int) -> str:
    """The package status as the package view (and so the API) reports it."""
    return lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, advisory_no).status


def test_issuing_an_advisory_opens_its_package(seeded: SeededScenario) -> None:
    seeded.issue_until(1)

    view = lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, 1)

    assert view.status == "open"
    assert view.decides_as_commander == "director"
    assert any(v.item.status == "pending" for v in view.items)


def test_a_refused_decision_changes_nothing(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    target = item(seeded, 1, "P-4.1")
    before = snapshot(seeded)

    with pytest.raises(DecisionRefused):
        decide(seeded, 1, target, "incident_commander", "approve")

    assert snapshot(seeded) == before


def test_a_decision_writes_one_audit_record(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    target = item(seeded, 1, "P-4.1")
    _, _, events_before = snapshot(seeded)

    decide(seeded, 1, target, "planning", "approve")

    seeded.session.expire_all()
    new = seeded.session.exec(
        select(AuditEvent).where(col(AuditEvent.id).not_in(events_before))
    ).all()
    assert [(e.type, e.payload["item_id"]) for e in new] == [("decision", target.id)]
    assert item(seeded, 1, "P-4.1").status == "approved"


def test_a_decided_item_is_refused_and_the_package_stays_open(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    target = item(seeded, 1, "P-4.1")
    decide(seeded, 1, target, "planning", "approve")
    before = snapshot(seeded)

    with pytest.raises(AlreadyDecided):
        decide(seeded, 1, target, "director", "override", "changed my mind")

    assert snapshot(seeded) == before
    assert served_status(seeded, 1) == "open"


def test_a_decision_on_an_expired_package_is_refused(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    target = item(seeded, 1, "P-4.1")
    seeded.issue_until(2)
    before = snapshot(seeded)

    with pytest.raises(lifecycle.PackageClosed):
        decide(seeded, 1, target, "planning", "approve")

    assert snapshot(seeded) == before
    assert served_status(seeded, 1) == "closed"
    assert item(seeded, 1, "P-4.1").status == "not_decided"


def test_a_package_stays_open_until_the_next_advisory_once_every_item_is_decided(
    seeded: SeededScenario,
) -> None:
    """Deciding the last item leaves the situation report to approve, so the package does not
    close until the next advisory is issued."""
    seeded.issue_until(1)
    view = lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, 1)
    for v in view.items:
        if v.item.kind == "gap":
            decide(seeded, 1, v.item, "director", "override", "not this period")
    if view.proposed_activation_level:
        level = cast(Level, view.proposed_activation_level)
        lifecycle.declare(seeded.session, seeded.cycle, Declaration(level, "director"))
    seeded.session.expire_all()
    assert not any(i.status == "pending" for i in seeded.session.exec(select(PackageItem)))

    assert served_status(seeded, 1) == "open"

    seeded.issue_until(2)

    assert served_status(seeded, 1) == "closed"


def test_package_status_and_the_cycle_never_disagree(seeded: SeededScenario) -> None:
    def agree(advisory_no: int) -> None:
        served = served_status(seeded, advisory_no)
        seeded.session.expire_all()
        recorded = seeded.session.get(DecisionPackage, advisory_no)
        assert recorded is not None
        assert served == recorded.status
        assert (recorded.status == "open") == seeded.cycle.waiting(advisory_no)

    seeded.issue_until(1)
    agree(1)
    decide(seeded, 1, item(seeded, 1, "P-4.1"), "planning", "approve")
    agree(1)
    with pytest.raises(DecisionRefused):
        decide(seeded, 1, item(seeded, 1, "P-4.3"), "incident_commander", "approve")
    agree(1)
    seeded.issue_until(2)
    agree(1)
    agree(2)


def test_a_package_record_out_of_step_with_the_cycle_is_an_error(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    recorded = seeded.session.get(DecisionPackage, 1)
    assert recorded is not None
    recorded.status = "closed"
    seeded.session.add(recorded)
    seeded.session.commit()

    with pytest.raises(lifecycle.PackageOutOfStep):
        lifecycle.is_open(seeded.session, seeded.cycle, 1)
