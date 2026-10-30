"""What a finding asks for in the decision package: the item it becomes, its proposed action
and the state that would satisfy it, which approved items need field work and whether a site
is under stop-work. Callers never read the engine's predicates or detail keys."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.models import Advisory, Finding, ItemKind, PackageItem
from app.playbook.actions import StateChange as StateChange  # what satisfying_state returns
from app.playbook.actions import proposed_action
from app.playbook.actions import satisfying_state as _satisfying_state
from app.playbook.activation import activation_proposal
from app.playbook.engine import prohibitions_in_force
from app.playbook.service import Playbook, RuleInputs, entity_names, rule_inputs

# The situation report rule: approving the report satisfies it, so it never becomes an item.
SITREP_RULE = "P-7.1"
# The staging area rule: an area forecast to flood is left (P-4.6), so crews no longer work from it.
RELOCATION_RULE = "P-4.6"
# The state keys a field crew completes on site (CR-02 C2): inspection, barrier, generator
# staging, relocation. An approved item that needs one of them is field work.
FIELD_WORK_KEYS = ("inspection_completed", "barrier_installed", "generator_assigned", "relocated")


def satisfying_state(playbook: Playbook, finding: Finding) -> list[StateChange]:
    """The state that would satisfy `finding`: one key for most rules, several together for
    some (P-6.2: the customer contacted and the hospital's backup confirmed), none for a
    proposal, which only a declaration closes (P-2.5)."""
    return _satisfying_state(playbook.rule(finding.rule_id), finding.entity_id, finding.details)


def actionable(finding: Finding) -> bool:
    """An open or conflicting finding: the EOC still has to act on it."""
    return finding.status != "satisfied"


def staging_to_leave(session: Session, advisory: Advisory) -> set[str]:
    """The staging areas the playbook has asked to leave (P-4.6, forecast to flood) at any
    advisory up to `advisory`."""
    return set(
        session.exec(
            select(Finding.entity_id).where(
                Finding.rule_id == RELOCATION_RULE,
                Finding.advisory_no <= advisory.advisory_no,
            )
        )
    )


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
    names = entity_names(session)
    items = []
    for finding in stored:
        if not actionable(finding) or finding.rule_id == SITREP_RULE:
            continue
        rule = playbook.rule(finding.rule_id)
        name = names.get(finding.entity_id)
        # the action text names an asset; the event and staging areas go by their ID
        asset = name and finding.entity_kind == "asset"
        label = f"{finding.entity_id} {name}" if asset else finding.entity_id
        conflict = finding.status == "conflict"
        kind: ItemKind = "conflict" if conflict else "gap"
        owner_role = finding.owner_role
        if rule.kind == "proposal":
            kind, owner_role = "proposal", activation_proposal(finding.details).declared_by
        action = proposed_action(rule, label, finding.details, finding.cites if conflict else None)
        items.append(ProposedItem(finding, kind, owner_role, action))
    return items


def stop_work(
    session: Session, advisory: Advisory, playbook: Playbook, entity_id: str
) -> list[str]:
    """The prohibitions in force at a site at `advisory` (P-4.7: tropical-storm-force wind within
    12 hours), as clause IDs; empty when work may go ahead."""
    return _stop_work(playbook, rule_inputs(session, advisory, playbook), entity_id)


def _stop_work(playbook: Playbook, inputs: RuleInputs, entity_id: str) -> list[str]:
    entity = next((e for e in inputs.entities if e.id == entity_id), None)
    if entity is None:
        return []
    return [r.id for r in prohibitions_in_force(playbook.rulebook, inputs.event, entity)]


@dataclass(frozen=True)
class FieldWork:
    """An approved item a field crew carries out: the state on its entity that completes it,
    and the prohibitions that stop work at its site at the advisory asked about (empty when
    none)."""

    item: PackageItem
    completes: list[StateChange]
    stop_work: list[str]


def field_work(session: Session, advisory: Advisory, playbook: Playbook) -> list[FieldWork]:
    """The approved items that need field work (inspection, barrier, generator staging,
    relocation) in the packages up to and including `advisory`'s, oldest first, with stop-work
    as it stands at `advisory`: work approved at advisory 3 is stopped at advisory 5 once
    tropical-storm-force wind is due within 12 hours."""
    approved = session.exec(
        select(PackageItem, Finding)
        .where(
            PackageItem.finding_id == Finding.id,
            PackageItem.advisory_no <= advisory.advisory_no,
            PackageItem.status == "approved",
        )
        .order_by(col(PackageItem.id))
    ).all()
    inputs = rule_inputs(session, advisory, playbook)
    work = []
    for item, finding in approved:
        completes = [
            c
            for c in satisfying_state(playbook, finding)
            if c.entity == item.entity_id and c.key in FIELD_WORK_KEYS
        ]
        if completes:
            work.append(FieldWork(item, completes, _stop_work(playbook, inputs, item.entity_id)))
    return work
