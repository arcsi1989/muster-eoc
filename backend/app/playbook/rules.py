"""Typed view of data/playbook/playbook_rules.yaml (never edited by code)."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

Op = Literal["eq", "ne", "gt", "ge", "lt", "le", "in", "contains_any", "is_true", "is_false"]
EntityKind = Literal["event", "asset", "staging_area"]
RuleKind = Literal["process", "action", "prohibition", "notification", "proposal"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Predicate(Strict):
    field: str  # namespace.name, e.g. asset.type
    op: Op
    value: Any = None
    value_field: str | None = None  # compare against another field instead of a value


class Deadline(Strict):
    field: str
    within_hours: float


class Rule(Strict):
    id: str
    title: str
    kind: RuleKind
    entity: EntityKind
    active_from_hours: float | None
    when: list[Predicate]
    satisfied_if: list[Predicate]
    requires_field_work: bool
    severity: str
    owner_role: str
    deadline: Deadline | None = None


class ConflictPolicy(Strict):
    clause: str
    rule: str
    resolution: str


class Rulebook(Strict):
    version: str
    document_id: str
    conflict_policy: ConflictPolicy
    rules: list[Rule]


def load_rulebook(path: Path) -> Rulebook:
    data = yaml.safe_load(path.read_text())
    return Rulebook.model_validate(
        {k: data[k] for k in ("version", "document_id", "conflict_policy", "rules")}
    )
