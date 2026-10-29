"""The shapes every LLM provider shares: what a draft is asked from, and what comes back."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


@dataclass(frozen=True)
class DraftRequest:
    """Everything a provider may see: plain data only, no database session, so no provider can
    write state (CLAUDE.md hard rules)."""

    advisory_no: int
    hours_to_landfall: int
    activation_level: str | None
    changes: dict[str, Any]
    items: list[DraftItem]
    top_assets: list[dict[str, Any]]  # id, name, rank, p_fail
    clauses: list[RetrievedClause]
    template_top_assets: int = 5
    feedback: list[str] = field(default_factory=list)  # validation problems from the last try


@dataclass(frozen=True)
class Grounding:
    """The clause and asset IDs a draft may cite: the findings, retrieved clauses, top assets."""

    clauses: set[str]
    assets: set[str]


@dataclass(frozen=True)
class DraftResult:
    draft: SitrepDraft
    provider: str
    model: str | None
    latency_ms: int
    usage: dict[str, int]


class LLMUnavailable(Exception):
    """The provider could not produce a usable draft (network, API error, refusal, no output)."""
