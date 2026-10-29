"""The action proposed for each gap, and the state an approval records (decisions.md: approval
counts the action as done from that moment)."""

from typing import Any

from app.playbook.activation import (
    DECLARED_BY,
    DECLARED_DETAIL,
    LEVEL_NUMBER,
    PROPOSED_DETAIL,
    Level,
)
from app.playbook.rules import Rule

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


def proposed_action(
    rule_id: str, entity_label: str, details: dict[str, Any], cites: list[str] | None = None
) -> str:
    fuelled = details.get("event.generators_fuelled", 0)
    needed = details.get("event.wtp_pump_stations_top25", 0)
    proposed: Level | None = details.get(PROPOSED_DETAIL)  # only P-2.5 has one
    text = ACTION_TEXT.get(rule_id, "Act on {entity} as the playbook requires").format(
        level_number=LEVEL_NUMBER[proposed] if proposed else None,
        proposed=proposed,
        declared=details.get(DECLARED_DETAIL),
        declarer=DECLARED_BY[proposed].replace("_", " ") if proposed else None,
        entity=entity_label,
        facilities=", ".join(details.get("asset.feeds_facility_ids", [])) or "critical facilities",
        fuelled=fuelled,
        needed=needed,
        missing=max(0, needed - fuelled),
    )
    if cites and len(cites) > 2:
        return CONFLICT_TEXT.format(action=text, prohibitions=", ".join(cites[1:-1]))
    return text


def approval_state(rule: Rule, details: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """(namespace, key) -> value that makes the rule's satisfied_if hold. Namespaces: "state"
    (the entity's own state) and "event"."""
    changes: dict[tuple[str, str], Any] = {}
    for predicate in rule.satisfied_if:
        namespace, _, key = predicate.field.partition(".")
        if predicate.op == "is_true":
            changes[(namespace, key)] = True
        elif predicate.op == "is_false":
            changes[(namespace, key)] = False
        elif predicate.value_field and predicate.op in ("ge", "eq"):
            changes[(namespace, key)] = details.get(predicate.value_field)
        elif predicate.op in ("eq", "ge"):
            changes[(namespace, key)] = predicate.value
        else:
            raise ValueError(f"{rule.id}: cannot derive an approval from {predicate.op}")
    return changes
