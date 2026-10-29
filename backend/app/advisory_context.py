"""The advisory context: which advisory is current, its scenario time and activation level, who
commands, and the per-advisory flags that hold for one operational period.

Every part of the app asks these questions here instead of working them out itself. `at` is
the one place the activation level of an advisory is decided.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session

from app.audit.log import record
from app.errors import ConflictError, DataNotLoaded
from app.models import Advisory, OpState, ScenarioState
from app.playbook.activation import FULL_ACTIVATION, ActivationLevel, activation_level

Commander = Literal["incident_commander", "director"]
COMMANDERS: tuple[Commander, Commander] = ("incident_commander", "director")
PER_ADVISORY_FLAGS = ("risk_list_reviewed_current", "sitrep_approved_current")


@dataclass(frozen=True)
class AdvisoryContext:
    advisory: Advisory | None  # None before advisory 1
    activation_level: str | None
    hours_since_full_activation: float | None

    @property
    def advisory_no(self) -> int:
        """0 before advisory 1."""
        return self.advisory.advisory_no if self.advisory else 0

    @property
    def scenario_time(self) -> int | None:
        """Hours to landfall at this advisory."""
        return self.advisory.hours_to_landfall if self.advisory else None

    @property
    def full_activation(self) -> bool:
        return self.activation_level == FULL_ACTIVATION

    @property
    def commander(self) -> Commander:
        """The Incident Commander at Full activation; the Director below it (P-2.3)."""
        return "incident_commander" if self.full_activation else "director"


def current_advisory_no(session: Session) -> int:
    """The current advisory's number, 0 before advisory 1."""
    state = session.get(ScenarioState, 1)
    if state is None:
        raise DataNotLoaded("scenario state missing; the gold data was not loaded")
    return state.current_advisory


def at(session: Session, levels: Sequence[ActivationLevel], advisory: Advisory) -> AdvisoryContext:
    """The context at an advisory, issued or not (the timeline shows the level ahead). The level
    is computed from hours to landfall; `session` is where a declared level would be read."""
    level = activation_level(advisory.hours_to_landfall, list(levels))
    full_from = next(lvl.from_hours for lvl in levels if lvl.name == FULL_ACTIVATION)
    return AdvisoryContext(
        advisory=advisory,
        activation_level=level,
        hours_since_full_activation=(
            full_from - advisory.hours_to_landfall if level == FULL_ACTIVATION else None
        ),
    )


def current(session: Session, levels: Sequence[ActivationLevel]) -> AdvisoryContext:
    """The context at the current advisory, or an empty one before advisory 1."""
    number = current_advisory_no(session)
    advisory = session.get(Advisory, number) if number else None
    if advisory is None:
        return AdvisoryContext(None, None, None)
    return at(session, levels, advisory)


def require_current(session: Session, advisory_no: int) -> None:
    """Raises if a newer advisory has been issued since `advisory_no`."""
    if advisory_no != current_advisory_no(session):
        raise ConflictError(f"advisory {advisory_no} is no longer current")


def reset_per_advisory_flags(session: Session, advisory: Advisory) -> None:
    """Risk list reviewed and situation report approved hold for one operational period."""
    record(
        session,
        "system",
        "per_advisory_flags_reset",
        "New operational period: risk list review and situation report approval reset",
        advisory,
        {"flags": list(PER_ADVISORY_FLAGS)},
        {},
    )
    for flag in PER_ADVISORY_FLAGS:
        session.merge(
            OpState(
                entity="event",
                key=flag,
                value=False,
                set_by=f"advisory {advisory.advisory_no}",
                set_at=advisory.issued_at,
            )
        )
