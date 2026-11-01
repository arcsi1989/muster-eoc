"""The shapes every LLM provider shares: what a draft is asked from, and what comes back."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import to_jsonable_python

from muster.classification import for_model
from muster.ids import CLAUSE_ID, SITE_ID, mentioned
from muster.replay.diff import AdvisoryChanges


@dataclass(frozen=True)
class Prompt:
    """A task's prompt and its settings, sent to a provider in the same shape for every task. The
    task that owns a prompt loads it; providers only send it."""

    version: str
    system: str
    max_tokens: int
    max_tool_rounds: int = 0  # model turns that may call tools before an answer is required
    deadline_s: float | None = None  # the whole answer, across tool rounds


class Paragraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="One paragraph of the situation report.")
    clause_ids: list[str] = Field(
        description="Every playbook clause ID the text mentions, e.g. P-4.2."
    )
    asset_ids: list[str] = Field(
        description="Every asset or staging area ID the text mentions, e.g. SUB-07, STG-02."
    )


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    paragraphs: list[Paragraph]


class SitrepDraft(BaseModel):
    """Structured output (CODING_STANDARDS L1): citations are data, not parsed from prose."""

    model_config = ConfigDict(extra="forbid")

    sections: list[Section]


class PackageDraft(SitrepDraft):
    """The draft situation report with its metadata: one model, stored in the decision package
    and served by the API as is. Frozen: a new draft replaces the stored one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["DRAFT"] = "DRAFT"  # the approved report is a Sitrep; the draft stays DRAFT
    provider: str  # the provider that wrote it, or "template (fallback)"
    fallback: bool  # the template draft replaced the provider's draft
    model: str | None
    prompt_version: str | None  # None for template drafts: no prompt is used
    fallback_reason: str | None

    def text(self) -> str:
        """The draft as editable plain text (headings, then paragraphs)."""
        blocks = []
        for section in self.sections:
            blocks.append(section.heading)
            blocks.extend(p.text for p in section.paragraphs)
        return "\n\n".join(blocks)


@dataclass(frozen=True)
class DraftItem:
    rule_id: str
    entity_id: str
    entity_is_citable: bool  # an asset or staging area (not the EOC-wide event)
    kind: str  # gap | conflict
    action: str
    cites: list[str]
    overdue: bool


@dataclass(frozen=True)
class RetrievedClause:
    id: str
    title: str
    text: str


HIDDEN = {"shown": False}  # field metadata: kept from the model, so never citable
QUOTED = {"citable": False}  # field metadata: shown to the model as data, never citable


@dataclass(frozen=True)
class FieldNote:
    """A field supervisor's note on a blocked field task: human free text, so quoted data that
    a draft may neither follow nor cite from."""

    rule_id: str
    entity_id: str
    note: str


@dataclass(frozen=True)
class TopAsset:
    id: str
    name: str
    rank: int
    p_fail: float


@dataclass(frozen=True)
class DraftRequest:
    """Everything a provider may see: plain data only, no database session, so no provider can
    write state (CLAUDE.md hard rules). What it shows is exactly what a draft may cite, except
    the quoted field notes."""

    advisory_no: int
    hours_to_landfall: int
    activation_level: str | None
    changes: AdvisoryChanges
    items: list[DraftItem]
    top_assets: list[TopAsset]
    clauses: list[RetrievedClause]
    # Blocked field tasks reported before this advisory, with the supervisor's note.
    field_reports: list[FieldNote] = field(default_factory=list, metadata=QUOTED)
    # Not shown: validation problems from the last try (a rejection, not data to cite).
    feedback: list[str] = field(default_factory=list, metadata=HIDDEN)

    def shown(self) -> dict[str, Any]:
        """The data a provider shows the model, without restricted fields (CR-03 C1)."""
        shown = {
            f.name: getattr(self, f.name) for f in fields(self) if f.metadata.get("shown", True)
        }
        return for_model(dict(to_jsonable_python(shown)))

    def _shown_text(self) -> str:
        """What is shown, without the quoted fields: the text a draft may cite from."""
        quoted = {f.name for f in fields(self) if not f.metadata.get("citable", True)}
        citable = {k: v for k, v in self.shown().items() if k not in quoted}
        return json.dumps(citable, default=str)

    @property
    def citable_clauses(self) -> frozenset[str]:
        return mentioned(CLAUSE_ID, self._shown_text())

    @property
    def citable_sites(self) -> frozenset[str]:
        """Assets and staging areas; facilities are named in the text only (prompt sitrep-v2)."""
        return mentioned(SITE_ID, self._shown_text())


@dataclass(frozen=True)
class DraftResult:
    draft: SitrepDraft
    provider: str
    model: str | None
    prompt_version: str | None  # the prompt the draft was written with; None for the template
    latency_ms: int
    usage: dict[str, int]


def attempt_tokens(attempt: dict[str, Any]) -> tuple[int, int]:
    """Input and output tokens of one entry of grounded generation's attempt log (zero for an
    attempt that failed before the provider reported usage)."""
    usage = attempt.get("usage") or {}
    return usage.get("input_tokens", 0), usage.get("output_tokens", 0)


class LLMUnavailable(Exception):
    """The provider could not produce a usable draft (network, API error, refusal, no output)."""


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


# Runs a read-only copilot tool by name; returns its data, or {"error": ...} if it can't answer.
ToolRunner = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ChatResult:
    text: str
    tools_used: list[str]
    model: (
        str | None
    )  # the model that answered (a refusal fallback can differ from the configured one)
    prompt_version: str | None  # the prompt the answer was written with; None for the template
    latency_ms: int
    usage: dict[str, int]


class IapObjective(BaseModel):
    """One incident objective of the IAP draft: its wording and the clauses and sites it cites.
    The citations come from the findings, never from a model."""

    text: str
    clause_ids: list[str]
    entity_ids: list[str]


class ObjectiveWording(BaseModel):
    """A model's rewording of the IAP objectives: one text per objective, in the same order."""

    texts: list[str] = Field(
        description=(
            "One reworded objective per objective given, in the same order. Mention only the "
            "clause and site IDs that objective cites."
        )
    )


@dataclass(frozen=True)
class ObjectivesRequest:
    """The objectives to reword, built by deterministic code; what each may cite is its own
    clause and entity IDs."""

    advisory_no: int
    objectives: list[IapObjective]
    # Not shown: validation problems from the last try.
    feedback: list[str] = field(default_factory=list, metadata=HIDDEN)

    def shown(self) -> dict[str, Any]:
        """The data a provider shows the model, without restricted fields (CR-03 C1)."""
        return for_model(
            {
                "advisory_no": self.advisory_no,
                "objectives": [o.model_dump() for o in self.objectives],
            }
        )


@dataclass(frozen=True)
class ObjectivesResult:
    wording: ObjectiveWording
    provider: str
    model: str | None
    prompt_version: str | None  # None for the template, which keeps the wording
    latency_ms: int
    usage: dict[str, int]
