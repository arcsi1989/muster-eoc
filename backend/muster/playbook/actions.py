"""What a finding asks for: the action proposed for it and the state that satisfies it
(decisions.md: approval counts the action as done from that moment). Internal to the playbook
module; callers use the interface in `muster.playbook.service`. It reads the engine's predicate
and detail-key formats so that no other module has to."""

from dataclasses import dataclass
from typing import Any

from muster.playbook.activation import LEVEL_NUMBER, activation_proposal
from muster.playbook.rules import Rule

ACTION_TEXT = {
    "P-2.5": (
        "Declare activation Level {level_number} ({proposed}), now {declared}; "
        "the {declarer} declares it"
    ),
    "P-4.1": "Review the ranked risk list for this advisory and record the review",
    "P-4.2": "Pre-inspect {entity}: pumps, controls and the flood door, before crews withdraw",
    "P-4.3": "Fuel {missing} more portable generators ({needed} needed, {fuelled} fuelled)",
    "P-4.4": "Inspect {entity}",
    "P-4.5": "Assign a portable generator to {entity} (feeds {facilities})",
    "P-4.6": "Move crews and equipment out of {entity} to an inland staging area",
    "P-5.1": "Install temporary flood barriers at {entity}",
    "P-5.2": "Confirm backup power and remote monitoring at {entity}",
    "P-5.3": "Confirm 7 days of treatment chemicals and a ready boil-water notice at {entity}",
    "P-6.2": (
        "Contact the hospitals fed by {entity} ({facilities}); confirm on-site backup power "
        "is tested with 96 hours of fuel, and record who, when and what was confirmed"
    ),
    "P-7.2": "Notify the state utility commission and record the time of notification",
}
CONFLICT_TEXT = (
    "{action}: blocked by stop-work ({prohibitions}). The Incident Commander decides: defer "
    "(crews withdraw) or an alternative measure. Personnel safety prevails (P-8.2)."
)


@dataclass(frozen=True)
class StateChange:
    """One operational state key and the value that satisfies a finding. `entity` is "event"
    or the finding's own entity."""

    entity: str
    key: str
    value: Any


def proposed_action(
    rule: Rule, entity_label: str, details: dict[str, Any], cites: list[str] | None = None
) -> str:
    """The action text for a finding; `cites` given for a conflict names its prohibitions."""
    fuelled = details.get("event.generators_fuelled", 0)
    needed = details.get("event.wtp_pump_stations_top25", 0)
    levels: dict[str, Any] = {}
    if rule.kind == "proposal":
        proposal = activation_proposal(details)
        levels = {
            "level_number": LEVEL_NUMBER[proposal.proposed],
            "proposed": proposal.proposed,
            "declared": proposal.declared,
            "declarer": proposal.declared_by.replace("_", " "),
        }
    text = ACTION_TEXT.get(rule.id, "Act on {entity} as the playbook requires").format(
        **levels,
        entity=entity_label,
        facilities=", ".join(details.get("asset.feeds_facility_ids", [])) or "critical facilities",
        fuelled=fuelled,
        needed=needed,
        missing=max(0, needed - fuelled),
    )
    if cites and len(cites) > 2:
        return CONFLICT_TEXT.format(action=text, prohibitions=", ".join(cites[1:-1]))
    return text


def satisfying_state(rule: Rule, entity_id: str, details: dict[str, Any]) -> list[StateChange]:
    """The state that makes the rule's satisfied_if hold for `entity_id`: one change per
    predicate (two for P-6.2), none for a proposal, which no state satisfies (P-2.5)."""
    if rule.kind == "proposal":
        return []
    changes = []
    for predicate in rule.satisfied_if:
        namespace, _, key = predicate.field.partition(".")
        entity = "event" if namespace == "event" else entity_id
        if predicate.op == "is_true":
            value: Any = True
        elif predicate.op == "is_false":
            value = False
        elif predicate.value_field and predicate.op in ("ge", "eq"):
            value = details.get(predicate.value_field)
        elif predicate.op in ("eq", "ge"):
            value = predicate.value
        else:
            raise ValueError(f"{rule.id}: cannot derive the satisfying state from {predicate.op}")
        changes.append(StateChange(entity, key, value))
    return changes
