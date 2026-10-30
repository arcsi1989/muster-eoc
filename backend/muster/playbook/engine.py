"""Deterministic playbook rule engine: the semantics at the top of playbook_rules.yaml.

- A rule is ACTIVE when event.hours_to_landfall <= active_from_hours (null: always).
- For each entity in scope, it MATCHES when every `when` predicate holds; a matched rule is
  SATISFIED when every `satisfied_if` predicate holds, otherwise OPEN.
- Prohibitions never become findings: they BLOCK open rules with requires_field_work on the same
  entity, which become CONFLICT findings citing both clauses and the conflict clause (P-8.2).
- A deadline that has passed on an open rule makes it overdue and escalates it to critical.
- A proposal (P-2.5) is never satisfied by data: only a person's declaration closes it.
The LLM never evaluates these rules.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from muster.playbook.rules import EntityKind, Predicate, Rule, Rulebook

Status = Literal["open", "satisfied", "conflict"]
Values = dict[str, dict[str, Any]]  # namespace -> field -> value


@dataclass(frozen=True)
class Entity:
    id: str
    kind: EntityKind
    values: Values  # asset / exposure / state / staging namespaces for this entity


@dataclass(frozen=True)
class Finding:
    rule_id: str
    entity_id: str
    entity_kind: EntityKind
    status: Status
    severity: str
    owner_role: str
    cites: list[str]  # clause IDs: the rule's own, plus the prohibition and P-8.2 for a conflict
    overdue: bool = False
    details: dict[str, Any] = field(default_factory=dict)  # the values the decision was based on


_MISSING = object()
INCIDENT_COMMANDER = "incident_commander"


def resolve(values: Values, path: str) -> Any:
    namespace, _, name = path.partition(".")
    return values.get(namespace, {}).get(name, _MISSING)


def holds(predicate: Predicate, values: Values) -> bool:
    """A predicate on a missing or null field never holds (is_false needs an explicit false)."""
    actual = resolve(values, predicate.field)
    if actual is _MISSING or actual is None:
        return False
    expected = resolve(values, predicate.value_field) if predicate.value_field else predicate.value
    if expected is _MISSING:
        return False
    match predicate.op:
        case "is_true":
            return actual is True
        case "is_false":
            return actual is False
        case "eq":
            return bool(actual == expected)
        case "ne":
            return bool(actual != expected)
        case "in":
            return isinstance(expected, list | tuple | set) and actual in expected
        case "contains_any":
            # list membership, never substring matching on text
            return (
                isinstance(actual, list | tuple | set)
                and isinstance(expected, list | tuple | set)
                and any(item in actual for item in expected)
            )
    if expected is None:
        return False
    match predicate.op:
        case "gt":
            return bool(actual > expected)
        case "ge":
            return bool(actual >= expected)
        case "lt":
            return bool(actual < expected)
        case "le":
            return bool(actual <= expected)
    raise ValueError(f"unknown operator {predicate.op}")


def _active(rule: Rule, event: dict[str, Any]) -> bool:
    return rule.active_from_hours is None or event["hours_to_landfall"] <= rule.active_from_hours


def _details(rule: Rule, values: Values) -> dict[str, Any]:
    fields = [p.field for p in (*rule.when, *rule.satisfied_if)]
    fields += [p.value_field for p in (*rule.when, *rule.satisfied_if) if p.value_field]
    if rule.deadline:
        fields.append(rule.deadline.field)
    if "asset.feeds_facility_types" in fields:
        fields.append("asset.feeds_facility_ids")  # which facility, e.g. HOSP-01
    found = {f: resolve(values, f) for f in fields}
    details = {f: v for f, v in found.items() if v is not _MISSING}
    if rule.deadline:
        details["deadline_within_hours"] = rule.deadline.within_hours
    return details


def prohibitions_in_force(rulebook: Rulebook, event: dict[str, Any], entity: Entity) -> list[Rule]:
    """The active prohibitions whose `when` holds for `entity` (P-4.7 stop-work)."""
    values = {**entity.values, "event": event}
    return [
        r
        for r in rulebook.rules
        if r.kind == "prohibition"
        and r.entity == entity.kind
        and _active(r, event)
        and all(holds(p, values) for p in r.when)
    ]


def evaluate(rulebook: Rulebook, event: dict[str, Any], entities: list[Entity]) -> list[Finding]:
    """Findings for one advisory: one per active, matched rule and entity in scope."""
    event_entity = Entity("event", "event", {})
    scope: dict[EntityKind, list[Entity]] = {
        "event": [event_entity],
        "asset": [],
        "staging_area": [],
    }
    for entity in entities:
        scope[entity.kind].append(entity)

    def values_for(entity: Entity) -> Values:
        return {**entity.values, "event": event}

    active = [r for r in rulebook.rules if _active(r, event)]
    blocked: dict[str, list[Rule]] = {}  # entity id -> prohibitions in force there
    for entity in (event_entity, *entities):
        if prohibitions := prohibitions_in_force(rulebook, event, entity):
            blocked[entity.id] = prohibitions

    findings = []
    for rule in (r for r in active if r.kind != "prohibition"):
        for entity in scope[rule.entity]:
            values = values_for(entity)
            if not all(holds(p, values) for p in rule.when):
                continue
            satisfied = rule.kind != "proposal" and all(holds(p, values) for p in rule.satisfied_if)
            status: Status = "satisfied" if satisfied else "open"
            cites = [rule.id]
            severity = rule.severity
            overdue = False
            owner_role = rule.owner_role
            if not satisfied and rule.requires_field_work and entity.id in blocked:
                prohibitions = blocked[entity.id]
                status = "conflict"
                cites = [rule.id, *(p.id for p in prohibitions), rulebook.conflict_policy.clause]
                severity = prohibitions[0].severity  # the prohibition's (P-4.7: critical)
                owner_role = INCIDENT_COMMANDER  # conflict_policy: route_to_incident_commander
            if not satisfied and rule.deadline:
                elapsed = resolve(values, rule.deadline.field)
                if isinstance(elapsed, int | float) and elapsed > rule.deadline.within_hours:
                    overdue, severity = True, "critical"
            findings.append(
                Finding(
                    rule_id=rule.id,
                    entity_id=entity.id,
                    entity_kind=entity.kind,
                    status=status,
                    severity=severity,
                    owner_role=owner_role,
                    cites=cites,
                    overdue=overdue,
                    details=_details(rule, values),
                )
            )
    return findings
