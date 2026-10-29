"""Who may decide what (decisions.md, P-2.5, P-3.x, P-8.1, P-8.2), and applying a decision."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, get_args

from sqlmodel import Session

from app.advisory_context import ACTIVATION_LEVEL, COMMANDERS, DECLARED_AT_HOURS, Commander
from app.errors import AppError, ConflictError
from app.models import Advisory, Finding, ItemStatus, OpState, PackageItem
from app.playbook.activation import LEVEL_NUMBER, Level, activation_proposal
from app.playbook.package import StateChange

Role = Literal[Commander, "planning", "operations", "logistics", "regulatory_liaison"]
Action = Literal["approve", "override", "defer", "alternative"]
DECIDED: set[ItemStatus] = set(get_args(ItemStatus)) - {"pending"}
DECIDED_BY_ACTION: dict[Action, ItemStatus] = {
    "approve": "approved",
    "override": "overridden",
    "defer": "deferred",
    "alternative": "alternative",
}


def role_label(role: str) -> str:
    """A role as audit summaries write it: "incident_commander" -> "Incident commander"."""
    return role.replace("_", " ").capitalize()


class DecisionRefused(AppError):
    status = 403
    code = "decision_refused"


class AlreadyDecided(ConflictError):
    code = "already_decided"


@dataclass(frozen=True)
class DecisionRequest:
    role: Role
    action: Action
    reason: str | None = None


@dataclass(frozen=True)
class Declaration:
    """A person declares an activation level (P-2.5)."""

    level: Level
    declared_by: Role
    reason: str | None = None


def check(item: PackageItem, request: DecisionRequest, lead: Commander) -> None:
    """Raises if this role may not take this decision on this item, with `lead` the role that
    commands at the advisory."""
    if item.status in DECIDED:
        raise AlreadyDecided(f"item {item.id} was already decided ({item.status})")
    if item.kind == "proposal":
        raise DecisionRefused(
            "An activation proposal is closed only by declaring the level (P-2.5)."
        )
    other_lead = next(role for role in COMMANDERS if role != lead)
    if request.role == other_lead:
        raise DecisionRefused(
            "The Incident Commander is appointed at full activation (P-2.3); below it the "
            f"Director decides. Choose the {lead.replace('_', ' ')} role."
        )
    reason = (request.reason or "").strip()
    if item.kind == "conflict":
        if request.role != lead:  # below Full activation the Director holds the IC's role
            raise DecisionRefused(
                f"Only the {lead.replace('_', ' ')} decides a conflict at this activation level "
                "(P-8.2)."
            )
        if request.action not in ("defer", "alternative"):
            raise DecisionRefused("A conflict is decided by deferring or an alternative measure.")
        if not reason:
            raise DecisionRefused("A conflict decision needs a reason (P-8.2).")
        return
    if request.action == "approve":
        if request.role not in (item.owner_role, lead):
            raise DecisionRefused(
                f"This action belongs to {item.owner_role.replace('_', ' ')}; that role or the "
                f"{lead.replace('_', ' ')} approves it."
            )
        return
    if request.action == "override":
        if request.role != lead:
            raise DecisionRefused(
                "An override is a deviation: only the "
                f"{lead.replace('_', ' ')} approves it (P-8.1)."
            )
        if not reason:
            raise DecisionRefused("An override needs a reason (P-8.1).")
        return
    raise DecisionRefused(f"{request.action} applies only to conflicts.")


def check_declaration(item: PackageItem, finding: Finding, declaration: Declaration) -> None:
    """Raises unless `declaration` declares the level the P-2.5 proposal `item` proposes, by the
    role that declares that level: the Director Level 3 and 2, the Incident Commander Level 1."""
    if item.status in DECIDED:
        raise AlreadyDecided(f"the activation proposal was already decided ({item.status})")
    proposal = activation_proposal(finding.details)
    proposed, declarer = proposal.proposed, proposal.declared_by
    number = LEVEL_NUMBER[proposed]
    if declaration.level != proposed:
        raise DecisionRefused(
            f"The playbook proposes Level {number} ({proposed}); declare that level or leave the "
            "proposal open (P-2.5)."
        )
    if declaration.declared_by != declarer:
        raise DecisionRefused(
            f"Level {number} ({proposed}) is declared by the {declarer.replace('_', ' ')} (P-2.5)."
        )


def declare(
    session: Session, item: PackageItem, declaration: Declaration, advisory: Advisory
) -> dict[str, object]:
    """Records the declaration on the P-2.5 item and writes the declared level and its scenario
    time. The only code that sets the activation level. Returns the state written."""
    now = datetime.now(UTC)
    item.status = "approved"
    item.decided_by = declaration.declared_by
    item.reason = (declaration.reason or "").strip() or None
    item.decided_at = now
    session.add(item)
    written: dict[str, object] = {
        ACTIVATION_LEVEL: declaration.level,
        DECLARED_AT_HOURS: advisory.hours_to_landfall,
    }
    for key, value in written.items():
        session.merge(
            OpState(
                entity="event", key=key, value=value, set_by=declaration.declared_by, set_at=now
            )
        )
    return {f"event.{key}": value for key, value in written.items()}


def apply(
    session: Session,
    item: PackageItem,
    request: DecisionRequest,
    satisfying: Sequence[StateChange],
) -> dict[str, object]:
    """Records the decision; an approval writes `satisfying`, the state the playbook says
    satisfies the item's finding. Returns the state changes made (empty for overrides and
    conflict decisions)."""
    now = datetime.now(UTC)
    item.status = DECIDED_BY_ACTION[request.action]
    item.decided_by = request.role
    item.reason = (request.reason or "").strip() or None
    item.decided_at = now
    session.add(item)
    if request.action != "approve":
        return {}
    written: dict[str, object] = {}
    for change in satisfying:
        session.merge(
            OpState(
                entity=change.entity,
                key=change.key,
                value=change.value,
                set_by=request.role,
                set_at=now,
            )
        )
        written[f"{change.entity}.{change.key}"] = change.value
    return written
