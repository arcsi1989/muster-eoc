"""Answers a copilot question through grounded generation: the provider calls read-only tools;
the answer may cite only IDs the tools returned. A failure or an ungrounded ID serves the
template answer (L9). This task owns the copilot prompt."""

import json
from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel import Session

from app import advisory_context
from app.agent.prompts import load_prompt
from app.audit.log import record
from app.copilot.tools import TOOL_DEFINITIONS, CopilotTools, ToolError, ToolOutput
from app.ids import ASSET_ID, CLAUSE_ID, ENTITY_ID, mentioned
from app.llm.grounded import generate
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatResult, ChatTurn, Prompt
from app.llm.template import TemplateProvider
from app.playbook.service import Playbook
from app.scoring_config import CopilotConfig, ScoringConfig

# A retry is sent the question again with what the validator found, as the draft is (L9).
_REJECTED = "\n\nYour previous answer was rejected:\n- "


def copilot_prompt(config: CopilotConfig) -> Prompt:
    return load_prompt(
        "copilot_v1",
        max_tokens=config.max_tokens,
        max_tool_rounds=config.max_tool_rounds,
        deadline_s=config.deadline_s,
    )


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
    """Runs tools for the provider and remembers the IDs they returned: asset and clause IDs,
    which become citations, and every ID anywhere in what a tool returned (an error that names
    an unknown asset included), which an answer may name: what the model is shown is citable."""

    def __init__(self, tools: CopilotTools) -> None:
        self._tools = tools
        self.asset_ids: set[str] = set()
        self.clause_ids: set[str] = set()
        self.other_ids: set[str] = set()

    def __call__(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            output: ToolOutput = self._tools.run(name, args)
        except ToolError as error:
            return self._shown({"error": str(error)})
        except TypeError:
            return {"error": f"wrong arguments for {name}"}
        self.asset_ids |= output.asset_ids
        self.clause_ids |= output.clause_ids
        self.other_ids |= output.other_ids
        return self._shown(output.data)

    def _shown(self, data: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(data, default=str)
        self.other_ids |= mentioned(ENTITY_ID, text) | mentioned(CLAUSE_ID, text)
        return data


@dataclass(frozen=True)
class _Answered:
    """A chat result with the recorder of the tools it ran, so it is checked against its own."""

    chat: ChatResult
    recorder: _Recorder

    @property
    def model(self) -> str | None:
        return self.chat.model

    @property
    def prompt_version(self) -> str | None:
        return self.chat.prompt_version

    @property
    def latency_ms(self) -> int:
        return self.chat.latency_ms

    @property
    def usage(self) -> dict[str, int]:
        return self.chat.usage


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


def _problems(answered: _Answered) -> list[str]:
    """The copilot's validator: an answer names only IDs its tools returned, and is not empty."""
    _, ungrounded = _cite(answered.chat.text, answered.recorder)
    problems = ["it names IDs no tool returned: " + ", ".join(ungrounded)] if ungrounded else []
    return problems + ([] if answered.chat.text else ["it has no text"])


def answer(
    session: Session,
    playbook: Playbook,
    provider: LLMProvider,
    question: str,
    history: list[ChatTurn],
    scoring: ScoringConfig,
) -> CopilotAnswer:
    config = scoring.copilot
    tools = CopilotTools(session, playbook, config)
    recent = history[-config.history_turns :]

    def ask(p: LLMProvider, prompt: Prompt, feedback: list[str]) -> _Answered:
        recorder = _Recorder(tools)  # each call is checked against the tools it ran
        asked = question + (_REJECTED + "\n- ".join(feedback) if feedback else "")
        return _Answered(p.chat(asked, recent, TOOL_DEFINITIONS, recorder, prompt), recorder)

    outcome = generate(
        provider,
        TemplateProvider.from_config(scoring),
        copilot_prompt(config),
        ask,
        _problems,
        1 + config.retries,
        rejected="the answer was not grounded",
        task="copilot",
    )
    result = outcome.result.chat
    citations, _ = _cite(result.text, outcome.result.recorder)

    advisory = advisory_context.current(session, playbook.levels).advisory
    record(
        session,
        "agent",
        "copilot_answered",
        f"Copilot ({outcome.provider}) answered: {question[:80]}",
        advisory,
        {
            "question": question,
            "provider": outcome.provider,
            "attempts": outcome.attempts,
            "tools_used": result.tools_used,
            "citations": [c.id for c in citations],
            "fallback_reason": outcome.fallback_reason,
        },
        {"prompt_version": outcome.prompt_version},
    )
    session.commit()
    return CopilotAnswer(
        result.text, citations, outcome.provider, outcome.fallback, result.tools_used
    )
