"""The shapes every LLM provider shares: what a draft is asked from, and what comes back."""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ids import CLAUSE_ID, SITE_ID, mentioned
from app.replay.diff import AdvisoryChanges


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


HIDDEN = {"shown": False}  # field metadata: kept from the model, so never citable


@dataclass(frozen=True)
class TopAsset:
    id: str
    name: str
    rank: int
    p_fail: float


@dataclass(frozen=True)
class DraftRequest:
    """Everything a provider may see: plain data only, no database session, so no provider can
    write state (CLAUDE.md hard rules). What it shows is exactly what a draft may cite."""

    advisory_no: int
    hours_to_landfall: int
    activation_level: str | None
    changes: AdvisoryChanges
    items: list[DraftItem]
    top_assets: list[TopAsset]
    clauses: list[RetrievedClause]
    # Not shown: the template's setting, and validation problems from the last try (a
    # rejection, not data to cite).
    template_top_assets: int = field(default=5, metadata=HIDDEN)
    feedback: list[str] = field(default_factory=list, metadata=HIDDEN)

    def shown(self) -> dict[str, Any]:
        """The data a provider shows the model."""
        data = asdict(self)
        return {f.name: data[f.name] for f in fields(self) if f.metadata.get("shown", True)}

    def _shown_text(self) -> str:
        return json.dumps(self.shown(), default=str)

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
    latency_ms: int
    usage: dict[str, int]


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
    prompt_version: str | None  # the copilot prompt's version; None for the template
    latency_ms: int
    usage: dict[str, int]
