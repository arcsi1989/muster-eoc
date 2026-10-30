"""The advisory context answers which advisory is current, its activation level and who
commands, and owns the per-advisory flags. Tested against a seeded scenario, without HTTP."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import select

from muster import advisory_context
from muster.agent.cycle import reset_scenario
from muster.models import (
    Advisory,
    AuditEvent,
    DecisionPackage,
    Finding,
    OpState,
    PackageItem,
    Score,
    Sitrep,
)
from tests import conftest
from tests.conftest import SeededScenario


def at_hours(seeded: SeededScenario, hours: int) -> advisory_context.AdvisoryContext:
    """The context at the current advisory 1, moved to `hours` to landfall."""
    seeded.issue_until(1)
    advisory = seeded.session.get(Advisory, 1)
    assert advisory is not None
    moved = advisory.model_copy(update={"hours_to_landfall": hours})
    return advisory_context.at(seeded.session, seeded.playbook.levels, moved)


def declared(seeded: SeededScenario, level: str, at_hours: int) -> None:
    """Operational state as a declaration leaves it (the declaration itself: test_activation)."""
    now = datetime.now(UTC)
    for key, value in (
        (advisory_context.ACTIVATION_LEVEL, level),
        (advisory_context.DECLARED_AT_HOURS, at_hours),
    ):
        seeded.session.merge(
            OpState(entity="event", key=key, value=value, set_by="director", set_at=now)
        )
    seeded.session.commit()


def test_before_advisory_1_there_is_no_current_advisory(seeded: SeededScenario) -> None:
    context = advisory_context.current(seeded.session, seeded.playbook.levels)

    assert context.advisory is None
    assert context.advisory_no == 0
    assert context.scenario_time is None
    assert context.activation_level == "monitor", "declared at the start of the scenario"
    assert context.proposed_activation_level is None
    assert not context.full_activation


def test_the_issued_advisory_becomes_current(seeded: SeededScenario) -> None:
    seeded.issue_until(2)

    context = advisory_context.current(seeded.session, seeded.playbook.levels)

    assert context.advisory_no == 2
    assert advisory_context.current_advisory_no(seeded.session) == 2
    assert context.scenario_time == 60
    assert context.activation_level == "monitor", "the level is declared, never reached"
    assert context.proposed_activation_level == "prepare"


@pytest.mark.parametrize(
    ("hours", "level"),
    [
        (121, None),
        (120, "monitor"),
        (73, "monitor"),
        (72, "prepare"),  # a threshold hour proposes the level it starts
        (49, "prepare"),
        (48, "full"),
        (0, "full"),
        (-3, "full"),  # the last level is proposed at landfall and after
    ],
)
def test_proposed_level_at_each_threshold(
    seeded: SeededScenario, hours: int, level: str | None
) -> None:
    context = at_hours(seeded, hours)

    assert context.proposed_activation_level == level
    assert context.activation_level == "monitor"


@pytest.mark.parametrize(
    ("level", "full", "commander"),
    [
        ("monitor", False, "director"),
        ("prepare", False, "director"),
        ("full", True, "incident_commander"),
    ],
)
def test_commander_follows_the_declared_level(
    seeded: SeededScenario, level: str, full: bool, commander: str
) -> None:
    declared(seeded, level, 72)

    context = at_hours(seeded, 24)  # whatever the thresholds propose

    assert context.activation_level == level
    assert context.full_activation is full
    assert context.commander == commander


def test_hours_since_full_activation_count_from_the_declaration(seeded: SeededScenario) -> None:
    assert at_hours(seeded, 36).hours_since_full_activation is None, "Full not declared"
    declared(seeded, "prepare", 72)
    assert at_hours(seeded, 36).hours_since_full_activation is None

    declared(seeded, "full", 44)

    assert at_hours(seeded, 44).hours_since_full_activation == 0
    assert at_hours(seeded, 32).hours_since_full_activation == 12


def test_an_advisory_not_yet_issued_has_no_declared_level(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    later = seeded.session.get(Advisory, 3)
    assert later is not None

    context = advisory_context.at(seeded.session, seeded.playbook.levels, later)

    assert context.activation_level is None
    assert context.proposed_activation_level == "full"


def test_a_new_advisory_resets_the_per_advisory_flags(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    for flag in advisory_context.PER_ADVISORY_FLAGS:
        seeded.session.merge(
            OpState(
                entity="event", key=flag, value=True, set_by="director", set_at=datetime.now(UTC)
            )
        )
    seeded.session.commit()

    seeded.issue_until(2)

    for flag in advisory_context.PER_ADVISORY_FLAGS:
        state = seeded.session.get(OpState, ("event", flag))
        assert state is not None
        assert state.value is False
        assert state.set_by == "advisory 2"


def test_scenario_reset_clears_every_module_and_returns_before_advisory_1(
    seeded: SeededScenario, tmp_path: Path
) -> None:
    seeded.issue_until(2)

    reset_scenario(seeded.session, seeded.cycle, conftest.test_settings(tmp_path).data_dir)

    assert advisory_context.current_advisory_no(seeded.session) == 0
    for table in (Score, Finding, DecisionPackage, PackageItem, Sitrep):
        assert seeded.session.exec(select(table)).first() is None
    events = seeded.session.exec(select(AuditEvent)).all()
    assert [e.type for e in events] == ["scenario_reset"]
    seeded.issue_until(1)  # the advisory cycle starts again from a clean thread
    assert seeded.session.get(DecisionPackage, 1) is not None
