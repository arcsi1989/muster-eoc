"""Answers a copilot question: the provider calls read-only tools; the answer may cite only IDs
the tools returned. A failure or an ungrounded ID serves the template answer (L9)."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel import Session

from app import advisory_context
from app.audit.log import record
from app.copilot.tools import TOOL_DEFINITIONS, CopilotTools, ToolError, ToolOutput
from app.ids import ASSET_ID, CLAUSE_ID, ENTITY_ID
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatResult, ChatTurn, LLMUnavailable
from app.llm.template import TemplateProvider
from app.models import Advisory
from app.playbook.service import Playbook
from app.scoring_config import CopilotConfig

log = logging.getLogger(__name__)
TEMPLATE_FALLBACK = "template (fallback)"


@dataclass(frozen=True)
class Citation:
    id: str
    kind: Literal["asset", "clause"]


@dataclass(frozen=True)
class CopilotAnswer:
    text: str
    citations: list[Citation]
    provider: str
    fallback: bool
    tools_used: list[str]


class _Recorder:
    """Runs tools for the provider and remembers every asset and clause ID they returned."""

    def __init__(self, tools: CopilotTools) -> None:
        self._tools = tools
        self.asset_ids: set[str] = set()
        self.clause_ids: set[str] = set()
        self.other_ids: set[str] = set()

    def __call__(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            output: ToolOutput = self._tools.run(name, args)
        except ToolError as error:
            return {"error": str(error)}
        except TypeError:
            return {"error": f"wrong arguments for {name}"}
        self.asset_ids |= output.asset_ids
        self.clause_ids |= output.clause_ids
        self.other_ids |= output.other_ids
        return output.data


def _cite(text: str, recorder: _Recorder) -> tuple[list[Citation], list[str]]:
    """Citations for the asset and clause IDs in the text that a tool returned, and every ID in
    the text no tool returned. A guard over the model's prose: what is cited still comes only from
    tool data (decisions.md)."""
    known = recorder.asset_ids | recorder.clause_ids | recorder.other_ids
    mentioned = [m.upper() for m in ENTITY_ID.findall(text) + CLAUSE_ID.findall(text)]
    ungrounded = [m for m in dict.fromkeys(mentioned) if m not in known]
    assets = dict.fromkeys(m.upper() for m in ASSET_ID.findall(text))
    clauses = dict.fromkeys(m.upper() for m in CLAUSE_ID.findall(text))
    citations = [Citation(m, "asset") for m in assets if m in recorder.asset_ids]
    citations += [Citation(m, "clause") for m in clauses if m in recorder.clause_ids]
    return citations, ungrounded


def answer(
    session: Session,
    playbook: Playbook,
    provider: LLMProvider,
    question: str,
    history: list[ChatTurn],
    config: CopilotConfig,
) -> CopilotAnswer:
    tools = CopilotTools(session, playbook, config)
    recorder = _Recorder(tools)
    template = TemplateProvider(config.top_risks_default)
    recent = history[-config.history_turns :]
    started = time.monotonic()
    attempt: dict[str, Any] = {"provider": provider.name, "model": provider.model}
    fallback_reason = None
    result: ChatResult | None = None
    try:
        result = provider.chat(question, recent, TOOL_DEFINITIONS, recorder)
        citations, ungrounded = _cite(result.text, recorder)
        attempt |= {
            "model": result.model,
            "latency_ms": result.latency_ms,
            "usage": result.usage,
            "tools": result.tools_used,
            "prompt_version": result.prompt_version,
        }
        if ungrounded and not isinstance(provider, TemplateProvider):
            fallback_reason = "the answer named IDs no tool returned: " + ", ".join(ungrounded)
        elif not result.text:
            fallback_reason = "the model returned no text"
    except Exception as error:  # noqa: BLE001 - any provider failure serves the template (L9)
        known = isinstance(error, LLMUnavailable)
        fallback_reason = str(error) if known else "unexpected provider error"
        attempt |= {
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": fallback_reason,
        }
        log.warning("copilot_fallback %s", attempt, exc_info=not known)

    label = provider.name
    if fallback_reason or result is None:
        recorder = _Recorder(tools)
        result = template.chat(question, recent, TOOL_DEFINITIONS, recorder)
        label = TEMPLATE_FALLBACK
    citations, _ = _cite(result.text, recorder)

    current = advisory_context.current_advisory_no(session)
    advisory = session.get(Advisory, current) if current else None
    record(
        session,
        "agent",
        "copilot_answered",
        f"Copilot ({label}) answered: {question[:80]}",
        advisory,
        {
            "question": question,
            "provider": label,
            "attempt": attempt,
            "tools_used": result.tools_used,
            "citations": [c.id for c in citations],
            "fallback_reason": fallback_reason,
        },
        {"prompt_version": result.prompt_version},
    )
    session.commit()
    return CopilotAnswer(
        result.text, citations, label, label == TEMPLATE_FALLBACK, result.tools_used
    )
