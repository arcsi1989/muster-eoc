"""The advisory context answers which advisory is current, its activation level and who
commands, and owns the per-advisory flags. Tested against a seeded scenario, without HTTP."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import select

from app import advisory_context
from app.agent.cycle import reset_scenario
from app.errors import ConflictError
from app.models import Advisory, DecisionPackage, Finding, OpState, PackageItem, Score
from tests import conftest
from tests.conftest import SeededScenario


def at_hours(seeded: SeededScenario, hours: int) -> advisory_context.AdvisoryContext:
    advisory = seeded.session.get(Advisory, 1)
    assert advisory is not None
    moved = advisory.model_copy(update={"hours_to_landfall": hours})
    return advisory_context.at(seeded.session, seeded.playbook.levels, moved)


def test_before_advisory_1_there_is_no_current_advisory(seeded: SeededScenario) -> None:
    context = advisory_context.current(seeded.session, seeded.playbook.levels)

    assert context.advisory is None
    assert context.advisory_no == 0
    assert context.scenario_time is None
    assert context.activation_level is None
    assert not context.full_activation


def test_the_issued_advisory_becomes_current(seeded: SeededScenario) -> None:
    seeded.issue_until(2)

    context = advisory_context.current(seeded.session, seeded.playbook.levels)

    assert context.advisory_no == 2
    assert advisory_context.current_advisory_no(seeded.session) == 2
    assert context.scenario_time == 60
    assert context.activation_level == "prepare"


@pytest.mark.parametrize(
    ("hours", "level"),
    [
        (121, None),
        (120, "monitor"),
        (73, "monitor"),
        (72, "prepare"),  # a boundary hour belongs to the later level
        (49, "prepare"),
        (48, "full"),
        (0, "full"),
        (-3, "full"),  # the lowest level also covers landfall and after
    ],
)
def test_activation_level_at_each_boundary_hour(
    seeded: SeededScenario, hours: int, level: str | None
) -> None:
    assert at_hours(seeded, hours).activation_level == level


@pytest.mark.parametrize(
    ("hours", "full", "commander"),
    [
        (100, False, "director"),
        (60, False, "director"),
        (48, True, "incident_commander"),
        (24, True, "incident_commander"),
    ],
)
def test_commander_per_level(
    seeded: SeededScenario, hours: int, full: bool, commander: str
) -> None:
    context = at_hours(seeded, hours)

    assert context.full_activation is full
    assert context.commander == commander


def test_hours_since_full_activation(seeded: SeededScenario) -> None:
    assert at_hours(seeded, 60).hours_since_full_activation is None
    assert at_hours(seeded, 48).hours_since_full_activation == 0
    assert at_hours(seeded, 36).hours_since_full_activation == 12


def test_require_current_refuses_an_earlier_advisory(seeded: SeededScenario) -> None:
    seeded.issue_until(2)

    advisory_context.require_current(seeded.session, 2)
    with pytest.raises(ConflictError, match="advisory 1 is no longer current"):
        advisory_context.require_current(seeded.session, 1)


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
    for table in (Score, Finding, DecisionPackage, PackageItem):
        assert seeded.session.exec(select(table)).first() is None
    seeded.issue_until(1)  # the advisory cycle starts again from a clean thread
    assert seeded.session.get(DecisionPackage, 1) is not None
