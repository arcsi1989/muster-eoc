"""The advisory context: which advisory is current, its scenario time and activation level, who
commands, and the per-advisory flags that hold for one operational period.

Every part of the app asks these questions here instead of working them out itself. The
activation level is the last level a person declared (P-2.5), read from operational state; this
module never sets it. The level the thresholds propose is given alongside.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, col, select

from app.audit.log import record
from app.errors import ConflictError, DataNotLoaded
from app.models import Advisory, Finding, OpState, PackageItem, ScenarioState
from app.playbook.activation import (
    DECLARED_DETAIL,
    FULL_ACTIVATION,
    PROPOSAL_RULE,
    PROPOSED_DETAIL,
    ActivationLevel,
    proposed_level,
)

Commander = Literal["incident_commander", "director"]
COMMANDERS: tuple[Commander, Commander] = ("incident_commander", "director")
PER_ADVISORY_FLAGS = ("risk_list_reviewed_current", "sitrep_approved_current")
# Operational state (entity "event") that only a declaration writes.
ACTIVATION_LEVEL = "activation_level"
DECLARED_AT_HOURS = "activation_declared_at_hours"  # hours to landfall when it was declared


@dataclass(frozen=True)
class AdvisoryContext:
    advisory: Advisory | None  # None before advisory 1
    activation_level: str | None  # declared; None for an advisory not yet issued
    proposed_activation_level: str | None  # from the propose_at_hours thresholds
    declared_at_hours: float | None = None  # scenario time of the declaration in force

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
    def hours_since_full_activation(self) -> float | None:
        """Counted from the Level 1 declaration; None below Full activation."""
        if not self.full_activation or self.declared_at_hours is None or self.advisory is None:
            return None
        return self.declared_at_hours - self.advisory.hours_to_landfall

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


def _declared(session: Session) -> tuple[str | None, float | None]:
    level = session.get(OpState, ("event", ACTIVATION_LEVEL))
    declared_at = session.get(OpState, ("event", DECLARED_AT_HOURS))
    return (level.value if level else None, declared_at.value if declared_at else None)


def _level_after(session: Session, advisory_no: int, declared_now: str | None) -> str | None:
    """The level in force when an earlier advisory's period ended. Each declaration closed that
    advisory's P-2.5 proposal, whose finding holds the level before and the level declared."""
    declarations = [
        (item.advisory_no, finding.details)
        for item, finding in session.exec(
            select(PackageItem, Finding)
            .where(
                PackageItem.finding_id == Finding.id,
                PackageItem.rule_id == PROPOSAL_RULE,
                PackageItem.status == "approved",
            )
            .order_by(col(PackageItem.advisory_no))
        )
    ]
    done = [details for number, details in declarations if number <= advisory_no]
    if done:
        declared: str | None = done[-1][PROPOSED_DETAIL]
        return declared
    if declarations:
        before: str | None = declarations[0][1][DECLARED_DETAIL]
        return before
    return declared_now


def at(session: Session, levels: Sequence[ActivationLevel], advisory: Advisory) -> AdvisoryContext:
    """The context at an advisory, issued or not (the timeline shows what lies ahead): at the
    current advisory the declared level; at an earlier one the level in force when its period
    ended; at a later one none yet."""
    proposed = proposed_level(advisory.hours_to_landfall, list(levels))
    current_no = current_advisory_no(session)
    if advisory.advisory_no > current_no:
        return AdvisoryContext(advisory, None, proposed)
    level, declared_at = _declared(session)
    if advisory.advisory_no < current_no:
        earlier = _level_after(session, advisory.advisory_no, level)
        return AdvisoryContext(advisory, earlier, proposed)
    return AdvisoryContext(advisory, level, proposed, declared_at)


def current(session: Session, levels: Sequence[ActivationLevel]) -> AdvisoryContext:
    """The context at the current advisory; before advisory 1 only the declared level."""
    number = current_advisory_no(session)
    advisory = session.get(Advisory, number) if number else None
    if advisory is None:
        level, declared_at = _declared(session)
        return AdvisoryContext(None, level, None, declared_at)
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
