"""The playbook module against a seeded session, without HTTP: the rule inputs (the namespace
the playbook rules read) at a seeded advisory, re-evaluating one finding after a state change,
what satisfies a finding, the package items findings produce, and field work and stop-work."""

from datetime import UTC, datetime

import pytest
from sqlmodel import select

from muster import advisory_context
from muster.agent import lifecycle
from muster.agent.decisions import DecisionRequest, Declaration
from muster.models import Advisory, Finding, OpState, PackageItem
from muster.playbook.package import (
    StateChange,
    field_work,
    package_items,
    satisfying_state,
    stop_work,
)
from muster.playbook.service import RuleInputs, entity_names, findings, reevaluate, rule_inputs
from tests.conftest import SeededScenario


def advisory(seeded: SeededScenario, advisory_no: int) -> Advisory:
    seeded.issue_until(advisory_no)
    issued = seeded.session.get(Advisory, advisory_no)
    assert issued is not None
    return issued


def inputs_at(seeded: SeededScenario, advisory_no: int) -> RuleInputs:
    return rule_inputs(seeded.session, advisory(seeded, advisory_no), seeded.playbook)


def stored(seeded: SeededScenario, advisory_no: int, rule_id: str, entity_id: str) -> Finding:
    seeded.session.expire_all()
    return next(
        f
        for f in findings(seeded.session, advisory_no)
        if (f.rule_id, f.entity_id) == (rule_id, entity_id)
    )


def write_state(seeded: SeededScenario, entity: str, key: str, value: object) -> None:
    seeded.session.merge(
        OpState(entity=entity, key=key, value=value, set_by="operations", set_at=datetime.now(UTC))
    )
    seeded.session.flush()


# Rule inputs


def test_an_asset_names_the_facilities_it_feeds(seeded: SeededScenario) -> None:
    inputs = inputs_at(seeded, 3)

    plant = inputs.entity("PS-09").values["asset"]
    hospital = inputs.entity("SUB-07").values["asset"]
    nothing = inputs.entity("PS-14").values["asset"]

    assert (plant["feeds_facility_types"], plant["feeds_facility_ids"]) == (
        ["treatment_plant"],
        ["WTP-01"],
    )
    assert (hospital["feeds_facility_types"], hospital["feeds_facility_ids"]) == (
        ["hospital"],
        ["HOSP-01"],
    )
    assert (nothing["feeds_facility_types"], nothing["feeds_facility_ids"]) == ([], [])


def test_pumping_stations_serving_the_plant_are_counted_in_the_top_25(
    seeded: SeededScenario,
) -> None:
    """PS-09 serves the treatment plant and moves from rank 28 to rank 20 (P-4.3)."""
    at_1 = inputs_at(seeded, 1)
    assert at_1.entity("PS-09").values["asset"]["risk_rank"] > 25
    assert at_1.event["wtp_pump_stations_top25"] == 8
    assert at_1.event["generators_fuelled"] == 6, "the generator gap at advisory 1"

    at_3 = inputs_at(seeded, 3)
    assert at_3.entity("PS-09").values["asset"]["risk_rank"] <= 25
    assert at_3.event["wtp_pump_stations_top25"] == 10


@pytest.mark.parametrize(("advisory_no", "proposed"), [(1, "prepare"), (3, "full")])
def test_the_proposed_level_differs_from_the_declared_one(
    seeded: SeededScenario, advisory_no: int, proposed: str
) -> None:
    event = inputs_at(seeded, advisory_no).event

    assert (event["activation_level"], event["proposed_activation_level"]) == ("monitor", proposed)


def test_hours_since_full_count_from_the_declaration(seeded: SeededScenario) -> None:
    assert inputs_at(seeded, 3).event["hours_since_full_activation"] is None, "only proposed"

    lifecycle.declare(seeded.session, seeded.cycle, Declaration("full", "incident_commander"))
    seeded.session.expire_all()

    at_3 = inputs_at(seeded, 3).event
    assert (at_3["activation_level"], at_3["hours_since_full_activation"]) == ("full", 0)
    assert inputs_at(seeded, 4).event["hours_since_full_activation"] == 12


@pytest.mark.parametrize("flag", advisory_context.PER_ADVISORY_FLAGS)
def test_per_advisory_flags_start_false_at_each_advisory(seeded: SeededScenario, flag: str) -> None:
    seeded.issue_until(1)
    write_state(seeded, "event", flag, True)
    seeded.session.commit()

    assert inputs_at(seeded, 2).event[flag] is False


# Re-evaluating one finding


def test_an_event_finding_is_satisfied_after_its_state_is_written(seeded: SeededScenario) -> None:
    issued = advisory(seeded, 1)
    assert stored(seeded, 1, "P-7.1", "event").status == "open"

    write_state(seeded, "event", advisory_context.SITREP_FLAG, True)
    finding = reevaluate(seeded.session, issued, seeded.playbook, "P-7.1")

    assert finding is not None
    assert (finding.status, finding.details) == (
        "satisfied",
        {"event.sitrep_approved_current": True},
    )
    seeded.session.rollback()
    assert stored(seeded, 1, "P-7.1", "event").status == "open", "the write was rolled back"


def test_an_asset_finding_is_satisfied_after_its_state_is_written(seeded: SeededScenario) -> None:
    issued = advisory(seeded, 3)
    assert stored(seeded, 3, "P-4.2", "PS-14").status == "open"

    write_state(seeded, "PS-14", "inspection_completed", True)
    finding = reevaluate(seeded.session, issued, seeded.playbook, "P-4.2", "PS-14")

    assert finding is not None and finding.status == "satisfied"
    seeded.session.commit()
    assert stored(seeded, 3, "P-4.2", "PS-14").status == "satisfied"


def test_a_re_evaluated_finding_keeps_its_conflict(seeded: SeededScenario) -> None:
    """The stop-work prohibition (P-4.7) still blocks the field work when one rule is re-run."""
    issued = advisory(seeded, 5)

    finding = reevaluate(seeded.session, issued, seeded.playbook, "P-4.2", "PS-14")

    assert finding is not None
    assert (finding.status, finding.cites) == ("conflict", ["P-4.2", "P-4.7", "P-8.2"])


def test_re_evaluating_a_finding_that_was_not_stored_finds_nothing(seeded: SeededScenario) -> None:
    issued = advisory(seeded, 1)

    assert reevaluate(seeded.session, issued, seeded.playbook, "P-7.2") is None


# What satisfies a finding


@pytest.mark.parametrize(
    ("advisory_no", "rule_id", "entity_id", "satisfying"),
    [
        (3, "P-4.2", "PS-14", [StateChange("PS-14", "inspection_completed", True)]),
        (
            3,
            "P-6.2",
            "SUB-07",
            [
                StateChange("SUB-07", "critical_customer_contacted", True),
                StateChange("SUB-07", "hospital_backup_confirmed", True),
            ],
        ),
        (3, "P-4.3", "event", [StateChange("event", "generators_fuelled", 10)]),
        (1, "P-2.5", "event", []),
    ],
    ids=["one key", "P-6.2 two keys", "event value from the rule inputs", "proposal none"],
)
def test_the_state_that_satisfies_a_finding(
    seeded: SeededScenario,
    advisory_no: int,
    rule_id: str,
    entity_id: str,
    satisfying: list[StateChange],
) -> None:
    seeded.issue_until(advisory_no)

    finding = stored(seeded, advisory_no, rule_id, entity_id)

    assert satisfying_state(seeded.playbook, finding) == satisfying


# Package items


def test_package_items_leave_out_the_situation_report_and_propose_the_level(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(1)
    at_1 = findings(seeded.session, 1)
    assert any(f.rule_id == "P-7.1" and f.status == "open" for f in at_1)

    items = {
        (p.finding.rule_id, p.finding.entity_id): p
        for p in package_items(seeded.session, seeded.playbook, at_1)
    }

    assert ("P-7.1", "event") not in items, "approving the situation report satisfies P-7.1"
    proposal = items[("P-2.5", "event")]
    assert (proposal.kind, proposal.owner_role, proposal.proposed_action) == (
        "proposal",
        "director",
        "Declare activation Level 2 (prepare), now monitor; the director declares it",
    )
    inspection = items[("P-4.4", "SUB-52")]
    assert (inspection.kind, inspection.proposed_action) == (
        "gap",
        "Inspect SUB-52 Lantern Hill South Substation",
    )


def test_one_name_lookup_for_assets_facilities_and_staging_areas(seeded: SeededScenario) -> None:
    names = entity_names(seeded.session)

    assert (names["PS-14"], names["WTP-01"], names["STG-02"]) == (
        "Seawall Pumping Station",
        "Bayport Water Treatment Plant",
        "Harborfront Yard",
    )
    assert "event" not in names


# Field work and stop-work


def item(seeded: SeededScenario, advisory_no: int, rule_id: str, entity_id: str) -> PackageItem:
    return next(
        i
        for i in seeded.session.exec(
            select(PackageItem).where(PackageItem.advisory_no == advisory_no)
        )
        if (i.rule_id, i.entity_id) == (rule_id, entity_id)
    )


def approve(seeded: SeededScenario, advisory_no: int, rule_id: str, entity_id: str) -> None:
    approved = item(seeded, advisory_no, rule_id, entity_id)
    request = DecisionRequest("operations", "approve")
    lifecycle.decide(
        seeded.session, seeded.playbook, seeded.cycle, advisory_no, approved.id or 0, request
    )


def test_an_approved_inspection_is_field_work_completed_by_its_state_key(
    seeded: SeededScenario,
) -> None:
    issued = advisory(seeded, 3)
    approve(seeded, 3, "P-4.2", "PS-14")
    approve(seeded, 3, "P-5.2", "PS-14")  # a confirmation from the EOC, not field work

    work = field_work(seeded.session, issued, seeded.playbook)

    assert [(w.item.rule_id, w.item.entity_id, w.completes, w.stop_work) for w in work] == [
        ("P-4.2", "PS-14", [StateChange("PS-14", "inspection_completed", True)], [])
    ], "only approved items that need a crew on site; the other P-4.2 items are pending"


def test_field_work_approved_earlier_is_stopped_once_stop_work_applies(
    seeded: SeededScenario,
) -> None:
    """PS-14's inspection approved at advisory 3 is still field work at advisory 5, where
    tropical-storm-force wind is due within 12 hours (P-4.7)."""
    seeded.issue_until(3)
    approve(seeded, 3, "P-4.2", "PS-14")

    at_5 = advisory(seeded, 5)
    work = {
        (w.item.advisory_no, w.item.rule_id, w.item.entity_id): w
        for w in field_work(seeded.session, at_5, seeded.playbook)
    }

    assert work[(3, "P-4.2", "PS-14")].stop_work == ["P-4.7"]


def test_ps14_is_under_stop_work_at_advisory_5(seeded: SeededScenario) -> None:
    at_3 = advisory(seeded, 3)
    assert stop_work(seeded.session, at_3, seeded.playbook, "PS-14") == []

    at_5 = advisory(seeded, 5)

    assert stop_work(seeded.session, at_5, seeded.playbook, "PS-14") == ["P-4.7"]
    assert stop_work(seeded.session, at_5, seeded.playbook, "event") == []
