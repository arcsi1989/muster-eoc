"""The golden set (backend/tests/evals/golden.yaml) and the evaluation thresholds
(config/evals.yaml): each case is an advisory state, a question or task, and machine-checkable
expectations."""

from pathlib import Path
from typing import Literal, Self, get_args

import yaml
from pydantic import Field, model_validator

from app.agent.decisions import Action, Role
from app.models import FieldStatus
from app.playbook.activation import Level
from app.scoring_config import Strict

Category = Literal["grounding", "refusal", "classification", "injection", "drafting"]
CATEGORIES: tuple[Category, ...] = get_args(Category)


def verdict(passed: bool) -> str:
    """A gate's outcome, as the report, the CLI and the audit log say it."""
    return "passed" if passed else "FAILED"


class RenameAsset(Strict):
    asset_id: str
    name: str


class Declare(Strict):
    level: Level
    role: Role


class Decide(Strict):
    rule_id: str
    entity_id: str
    role: Role
    action: Action


class ReportField(Strict):
    rule_id: str
    entity_id: str
    district: str
    outcome: FieldStatus
    note: str


class Step(Strict):
    """One thing that happens to the scenario at advisory `at` (0: before the first), before any
    case at that advisory runs. Exactly one action is set."""

    at: int = Field(ge=0)
    rename_asset: RenameAsset | None = None
    declare: Declare | None = None
    decide: Decide | None = None
    report_field: ReportField | None = None

    @model_validator(mode="after")
    def _one_action(self) -> Self:
        actions = [self.rename_asset, self.declare, self.decide, self.report_field]
        if sum(a is not None for a in actions) != 1:
            raise ValueError("a step has exactly one action")
        return self


class Expect(Strict):
    """What a run must show. Every check is a rule over the transcript; none asks a model."""

    ids_include: list[str] = []  # the answer names each of these asset, facility or clause IDs
    ids_equal: list[str] | None = None  # the answer names exactly these IDs
    contains: list[str] = []  # case-insensitive substrings the answer contains
    regex: list[str] = []  # patterns the answer matches
    not_regex: list[str] = []  # patterns the answer does not match
    tools_allowed: list[str] | None = None  # the only tools the turn may call
    # entities whose restricted values the answer never shows, beside every entity it names
    restricted_values_of: list[str] = []
    # On for every case: what the answer names and every number in it came from the turn's tool
    # results (or the draft request); only read-only tools were called and no state changed; no
    # tool result shown to the model held a restricted field.
    grounded: bool = True
    read_only: bool = True
    # Drafts only: marked DRAFT; every gap and conflict cited; "approved" only for approved items.
    draft_checks: bool = False


class Case(Strict):
    id: str
    category: Category
    advisory: int = Field(ge=1)
    task: Literal["copilot", "sitrep"]
    question: str | None = None  # the copilot question; a sitrep case drafts at `advisory`
    setup: list[Step] = []
    expect: Expect

    @model_validator(mode="after")
    def _question_for_copilot(self) -> Self:
        if (self.task == "copilot") != (self.question is not None):
            raise ValueError(f"{self.id}: a copilot case has a question, a sitrep case none")
        return self


class GoldenSet(Strict):
    cases: list[Case]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        ids = [c.id for c in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case IDs repeat")
        return self


class Gate(Strict):
    """A category passes at or above `min_pass_rate`, or at or below `max_failures` failed runs."""

    min_pass_rate: float | None = Field(default=None, ge=0, le=1)
    max_failures: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one_bound(self) -> Self:
        if (self.min_pass_rate is None) == (self.max_failures is None):
            raise ValueError("a gate has min_pass_rate or max_failures")
        return self

    def passes(self, passed: int, runs: int, failed_elsewhere: int = 0) -> bool:
        """`failed_elsewhere`: failures from other categories' runs that count against a
        zero-failure gate (a leak, an injected write)."""
        if self.max_failures is not None:
            return runs - passed + failed_elsewhere <= self.max_failures
        return runs > 0 and passed / runs >= (self.min_pass_rate or 0)


class Repeats(Strict):
    template: int = Field(ge=1)
    live: int = Field(ge=1)


class EvalConfig(Strict):
    repeats: Repeats
    gates: dict[Category, Gate]

    @model_validator(mode="after")
    def _every_category(self) -> Self:
        if set(self.gates) != set(CATEGORIES):
            raise ValueError(f"a gate for each category: {', '.join(CATEGORIES)}")
        return self


def load_golden(path: Path) -> GoldenSet:
    """Top-level keys starting with x- hold YAML anchors the cases reuse."""
    raw = yaml.safe_load(path.read_text())
    return GoldenSet.model_validate({k: v for k, v in raw.items() if not k.startswith("x-")})


def load_eval_config(path: Path) -> EvalConfig:
    return EvalConfig.model_validate(yaml.safe_load(path.read_text()))
