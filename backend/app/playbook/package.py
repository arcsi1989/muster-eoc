"""What a finding asks for in the decision package: the item it becomes, its proposed action
and the state that would satisfy it. Callers never read the engine's predicates or detail
keys."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session

from app.models import Finding, ItemKind
from app.network import load_network
from app.playbook.actions import StateChange as StateChange  # what satisfying_state returns
from app.playbook.actions import proposed_action
from app.playbook.actions import satisfying_state as _satisfying_state
from app.playbook.activation import activation_proposal
from app.playbook.service import Playbook

# The situation report rule: approving the report satisfies it, so it never becomes an item.
SITREP_RULE = "P-7.1"


def satisfying_state(playbook: Playbook, finding: Finding) -> list[StateChange]:
    """The state that would satisfy `finding`: one key for most rules, several together for
    some (P-6.2: the customer contacted and the hospital's backup confirmed), none for a
    proposal, which only a declaration closes (P-2.5)."""
    return _satisfying_state(playbook.rule(finding.rule_id), finding.entity_id, finding.details)


@dataclass(frozen=True)
class ProposedItem:
    """A package item the playbook proposes for one stored finding."""

    finding: Finding
    kind: ItemKind
    owner_role: str
    proposed_action: str


def package_items(
    session: Session, playbook: Playbook, stored: Sequence[Finding]
) -> list[ProposedItem]:
    """The items `stored` findings produce: one per open or conflicting finding, except the
    situation report rule (P-7.1), which approving the report satisfies. A P-2.5 finding is an
    activation proposal, owned by the role that declares the proposed level."""
    network = load_network(session)
    items = []
    for finding in stored:
        if finding.status == "satisfied" or finding.rule_id == SITREP_RULE:
            continue
        rule = playbook.rule(finding.rule_id)
        described = network.describe(finding.entity_id)
        label = f"{finding.entity_id} {described[1]}" if described else finding.entity_id
        conflict = finding.status == "conflict"
        kind: ItemKind = "conflict" if conflict else "gap"
        owner_role = finding.owner_role
        if rule.kind == "proposal":
            kind, owner_role = "proposal", activation_proposal(finding.details).declared_by
        action = proposed_action(rule, label, finding.details, finding.cites if conflict else None)
        items.append(ProposedItem(finding, kind, owner_role, action))
    return items
