"""The decision package lifecycle through a seeded session, without HTTP: one answer to "is the
package open", and the path every decision takes: item decisions, situation report approval
and activation declarations."""

from typing import Any, cast

import pytest
from sqlmodel import col, select

from muster import advisory_context
from muster.advisory_context import SITREP_FLAG
from muster.agent import lifecycle
from muster.agent.decisions import AlreadyDecided, DecisionRefused, DecisionRequest, Declaration
from muster.agent.sitrep import SitrepAlreadyApproved
from muster.llm.schemas import Paragraph
from muster.models import AuditEvent, DecisionPackage, Finding, OpState, PackageItem, Sitrep
from muster.playbook.activation import Level
from muster.playbook.package import SITREP_RULE
from tests.conftest import FakeProvider, SeededFactory, SeededScenario, draft_of


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


def approve_sitrep(seeded: SeededScenario, advisory_no: int, role: Any, text: str) -> Any:
    return lifecycle.approve_sitrep(
        seeded.session, seeded.playbook, seeded.cycle, advisory_no, role, text
    )


def sitrep_finding(seeded: SeededScenario, advisory_no: int) -> Finding:
    seeded.session.expire_all()
    return seeded.session.exec(
        select(Finding).where(Finding.advisory_no == advisory_no, Finding.rule_id == SITREP_RULE)
    ).one()


def new_events(seeded: SeededScenario, before: list[Any]) -> list[AuditEvent]:
    seeded.session.expire_all()
    return list(seeded.session.exec(select(AuditEvent).where(col(AuditEvent.id).not_in(before))))


def test_approving_the_situation_report_on_an_open_package_satisfies_p_7_1(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(1)
    assert sitrep_finding(seeded, 1).status == "open"
    _, _, events_before = snapshot(seeded)

    sitrep = approve_sitrep(seeded, 1, "director", "Situation report.")

    assert (sitrep.approved_by, sitrep.approved_text) == ("director", "Situation report.")
    assert sitrep_finding(seeded, 1).status == "satisfied"
    flag = seeded.session.get(OpState, ("event", SITREP_FLAG))
    assert flag is not None and (flag.value, flag.set_by) == (True, "director")
    assert [e.type for e in new_events(seeded, events_before)] == ["sitrep_approved"]
    assert served_status(seeded, 1) == "open", "the package stays open until the next advisory"


def test_approving_the_situation_report_on_a_closed_package_is_refused(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(2)
    before = snapshot(seeded)

    with pytest.raises(lifecycle.PackageClosed):
        approve_sitrep(seeded, 1, "director", "Situation report.")

    assert snapshot(seeded) == before
    assert seeded.session.get(Sitrep, 1) is None


@pytest.mark.parametrize("role", ["incident_commander", "planning"])
def test_the_situation_report_approved_by_the_wrong_role_is_refused(
    seeded: SeededScenario, role: str
) -> None:
    seeded.issue_until(1)
    before = snapshot(seeded)

    with pytest.raises(DecisionRefused):
        approve_sitrep(seeded, 1, role, "Situation report.")

    assert snapshot(seeded) == before
    assert sitrep_finding(seeded, 1).status == "open"


def test_a_situation_report_is_approved_once(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    approve_sitrep(seeded, 1, "director", "Situation report.")
    before = snapshot(seeded)

    with pytest.raises(SitrepAlreadyApproved):
        approve_sitrep(seeded, 1, "director", "Again.")

    assert snapshot(seeded) == before


@pytest.mark.parametrize(
    ("advisory_no", "level", "role"),
    [(1, "prepare", "incident_commander"), (3, "full", "director")],
)
def test_a_declaration_by_the_wrong_role_is_refused(
    seeded: SeededScenario, advisory_no: int, level: Level, role: Any
) -> None:
    """The Director declares Level 3 and 2, the Incident Commander Level 1 (P-2.5)."""
    seeded.issue_until(advisory_no)
    before = snapshot(seeded)

    with pytest.raises(DecisionRefused):
        lifecycle.declare(seeded.session, seeded.cycle, Declaration(level, role))

    assert snapshot(seeded) == before


def test_a_declaration_closes_the_proposal_with_one_audit_record(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    _, _, events_before = snapshot(seeded)

    lifecycle.declare(seeded.session, seeded.cycle, Declaration("prepare", "director", "T-72"))

    proposal = item(seeded, 1, "P-2.5")
    assert (proposal.status, proposal.decided_by) == ("approved", "director")
    assert [e.type for e in new_events(seeded, events_before)] == ["activation_declared"]
    context = advisory_context.current(seeded.session, seeded.playbook.levels)
    assert context.activation_level == "prepare"


def test_declaring_full_starts_the_p_7_2_clock(seeded: SeededScenario) -> None:
    seeded.issue_until(3)
    assert not any(v.item.rule_id == "P-7.2" for v in view_items(seeded, 3))

    lifecycle.declare(seeded.session, seeded.cycle, Declaration("full", "incident_commander"))

    regulator = item(seeded, 3, "P-7.2")
    assert regulator.status == "pending"
    seeded.session.expire_all()
    finding = seeded.session.get(Finding, regulator.finding_id)
    assert finding is not None
    assert finding.details["event.hours_since_full_activation"] == 0
    assert served_status(seeded, 3) == "open"


def test_no_lifecycle_operation_but_a_declaration_sets_the_activation_level(
    seeded: SeededScenario,
) -> None:
    """Every other lifecycle operation, at every advisory (item decisions, situation report
    approvals, issuing and expiring): the level's state row is never rewritten, not even with
    the same value."""

    def level() -> Any:
        seeded.session.expire_all()
        row = seeded.session.get(OpState, ("event", advisory_context.ACTIVATION_LEVEL))
        assert row is not None
        return row.value, row.set_by, row.set_at

    initial = level()
    assert initial[0] == "monitor"

    for advisory_no in range(1, 6):
        seeded.issue_until(advisory_no)
        assert level() == initial
        for v in view_items(seeded, advisory_no):
            if v.item.kind == "gap":
                decide(seeded, advisory_no, v.item, "director", "approve")
            elif v.item.kind == "conflict":
                decide(seeded, advisory_no, v.item, "director", "defer", "stop-work")
        approve_sitrep(seeded, advisory_no, "director", "Situation report.")
        assert level() == initial


def view_items(seeded: SeededScenario, advisory_no: int) -> list[lifecycle.ItemView]:
    return lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, advisory_no).items


def test_a_package_goes_through_its_whole_lifecycle_without_http(
    make_seeded: SeededFactory,
) -> None:
    """Open -> declare the proposed level -> decide an item -> approve the situation report ->
    closed by the next advisory, with the audit record each step writes."""
    paragraph = Paragraph(text="Storm preparation is under way.", clause_ids=[], asset_ids=[])
    with make_seeded(FakeProvider(draft_of(paragraph))) as seeded:
        seeded.issue_until(1)
        view = lifecycle.package_view(seeded.session, seeded.playbook, seeded.cycle, 1)
        draft = view.package.draft
        assert draft is not None
        assert (view.status, draft.provider) == ("open", "fake")
        assert view.proposed_activation_level == "prepare"
        _, _, events_before = snapshot(seeded)

        lifecycle.declare(seeded.session, seeded.cycle, Declaration("prepare", "director"))
        decide(seeded, 1, item(seeded, 1, "P-4.1"), "planning", "approve")
        sitrep = approve_sitrep(seeded, 1, "director", draft.text())
        seeded.issue_until(2)

        assert (sitrep.approved_by, sitrep.edited) == ("director", False)
        assert served_status(seeded, 1) == "closed"
        statuses = {v.item.rule_id: v.item.status for v in view_items(seeded, 1)}
        assert (statuses["P-2.5"], statuses["P-4.1"]) == ("approved", "approved")
        assert {s for r, s in statuses.items() if r not in ("P-2.5", "P-4.1")} == {"not_decided"}
        assert sitrep_finding(seeded, 1).status == "satisfied"
        events = [(e.advisory_no, e.type, e.summary) for e in new_events(seeded, events_before)]
        assert [(no, kind) for no, kind, _ in events] == [
            (1, "activation_declared"),
            (1, "decision"),
            (1, "sitrep_approved"),
            (1, "items_not_decided"),
            (1, "package_finalised"),
            (2, "per_advisory_flags_reset"),
            (2, "context_loaded"),
            (2, "diff"),
            (2, "rules_evaluated"),
            (2, "sitrep_drafted"),
        ]
        assert events[0][2] == "Director declared activation Level 2 (prepare)"
        assert events[1][2] == "Planning approved P-4.1 for " + item(seeded, 1, "P-4.1").entity_id
        assert events[2][2] == "Director approved the situation report as drafted"
        assert events[3][2].endswith("items closed as not decided when the next advisory arrived")
        assert events[4][2] == "Decision package for advisory 1 closed"
        assert events[9][2] == "Draft situation report written by fake"


# What a package item says and what approving it writes (pinned before the playbook module took
# over the action text and the satisfying state, architecture-deepening/19)


def op_state(seeded: SeededScenario, entity: str, key: str) -> object:
    seeded.session.expire_all()
    row = seeded.session.get(OpState, (entity, key))
    return row.value if row else None


def test_items_propose_their_action_and_approving_one_writes_its_satisfying_state(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(3)
    at_3 = {(v.item.rule_id, v.item.entity_id): v.item for v in view_items(seeded, 3)}

    proposal, generators, hospital = (
        at_3[("P-2.5", "event")],
        at_3[("P-4.3", "event")],
        at_3[("P-6.2", "SUB-07")],
    )
    assert (proposal.kind, proposal.owner_role, proposal.proposed_action) == (
        "proposal",
        "incident_commander",
        "Declare activation Level 1 (full), now monitor; the incident commander declares it",
    )
    assert generators.proposed_action == "Fuel 4 more portable generators (10 needed, 6 fuelled)"
    assert hospital.proposed_action == (
        "Contact the hospitals fed by SUB-07 Medical District Substation (HOSP-01); confirm "
        "on-site backup power is tested with 96 hours of fuel, and record who, when and what "
        "was confirmed"
    )

    decide(seeded, 3, generators, "logistics", "approve")
    decide(seeded, 3, hospital, "regulatory_liaison", "approve")

    assert op_state(seeded, "event", "generators_fuelled") == 10
    assert op_state(seeded, "SUB-07", "critical_customer_contacted") is True
    assert op_state(seeded, "SUB-07", "hospital_backup_confirmed") is True


def test_items_name_staging_areas_and_conflicts_by_their_clauses(seeded: SeededScenario) -> None:
    seeded.issue_until(4)
    at_4 = {(v.item.rule_id, v.item.entity_id): v for v in view_items(seeded, 4)}
    staging = at_4[("P-4.6", "STG-02")]
    assert (staging.entity_name, staging.item.proposed_action) == (
        "Harborfront Yard",
        "Move crews and equipment out of STG-02 to an inland staging area",
    ), "the view names the staging area; the action text gives its ID"

    seeded.issue_until(5)
    at_5 = {(v.item.rule_id, v.item.entity_id): v for v in view_items(seeded, 5)}
    conflict = at_5[("P-4.2", "PS-14")]

    assert (conflict.entity_name, conflict.item.kind, conflict.item.owner_role) == (
        "Seawall Pumping Station",
        "conflict",
        "incident_commander",
    )
    assert conflict.item.proposed_action == (
        "Pre-inspect PS-14 Seawall Pumping Station: pumps, controls and the flood door, before "
        "crews withdraw: blocked by stop-work (P-4.7). The Incident Commander decides: defer "
        "(crews withdraw) or an alternative measure. Personnel safety prevails (P-8.2)."
    )
