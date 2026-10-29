"""Who may decide what (decisions.md, P-3.x, P-8.1, P-8.2), and applying a decision."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlmodel import Session

from app.advisory_context import COMMANDERS, Commander
from app.agent.actions import approval_state
from app.errors import AppError, ConflictError
from app.models import Finding, OpState, PackageItem
from app.playbook.rules import Rule

Role = Literal[
    "incident_commander", "director", "planning", "operations", "logistics", "regulatory_liaison"
]
Action = Literal["approve", "override", "defer", "alternative"]
DECIDED = {"approved", "overridden", "deferred", "alternative", "not_decided"}


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


def check(item: PackageItem, request: DecisionRequest, lead: Commander) -> None:
    """Raises if this role may not take this decision on this item, with `lead` the role that
    commands at the advisory."""
    if item.status in DECIDED:
        raise AlreadyDecided(f"item {item.id} was already decided ({item.status})")
    other_lead = next(role for role in COMMANDERS if role != lead)
    if request.role == other_lead:
        raise DecisionRefused(
            "The Incident Commander is appointed at full activation (P-2.3); below it the "
            f"Director decides. Choose the {lead.replace('_', ' ')} role."
        )
    reason = (request.reason or "").strip()
    if item.kind == "conflict":
        if request.role != "incident_commander":
            raise DecisionRefused("Only the Incident Commander decides a conflict (P-8.2).")
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


def apply(
    session: Session, item: PackageItem, request: DecisionRequest, rule: Rule, finding: Finding
) -> dict[str, object]:
    """Records the decision; an approval writes the state that satisfies the rule. Returns the
    state changes made (empty for overrides and conflict decisions)."""
    now = datetime.now(UTC)
    item.status = {  # type: ignore[assignment]  # the map's values are all ItemStatus
        "approve": "approved",
        "override": "overridden",
        "defer": "deferred",
        "alternative": "alternative",
    }[request.action]
    item.decided_by = request.role
    item.reason = (request.reason or "").strip() or None
    item.decided_at = now
    session.add(item)
    if request.action != "approve":
        return {}
    changes = approval_state(rule, finding.details)
    written: dict[str, object] = {}
    for (namespace, key), value in changes.items():
        entity = "event" if namespace == "event" else item.entity_id
        session.merge(OpState(entity=entity, key=key, value=value, set_by=request.role, set_at=now))
        written[f"{entity}.{key}"] = value
    return written
