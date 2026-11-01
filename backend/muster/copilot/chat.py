"""Answers a copilot question through grounded generation: the provider calls read-only tools;
the answer may cite only IDs and state only numbers the tools returned. A failure, an ungrounded
ID or an ungrounded number serves the template answer (L9). This task owns the copilot prompt."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlmodel import Session

from muster import advisory_context
from muster.agent.prompts import load_prompt
from muster.audit.log import record
from muster.classification import for_model
from muster.copilot.tools import TOOL_DEFINITIONS, CopilotTools, ToolError, ToolOutput
from muster.ids import ASSET_ID, CLAUSE_ID, ENTITY_ID, mentioned
from muster.llm.grounded import GenerationEvent, generate
from muster.llm.provider import LLMProvider
from muster.llm.schemas import ChatResult, ChatTurn, Prompt
from muster.llm.template import TemplateProvider
from muster.numbers import ungrounded_numbers
from muster.playbook.service import Playbook
from muster.scoring_config import CopilotConfig, ScoringConfig

# A retry is sent the question again with what the validator found, as the draft is (L9).
_REJECTED = "\n\nYour previous answer was rejected:\n- "


def copilot_prompt(config: CopilotConfig) -> Prompt:
    return load_prompt(
        "copilot_v2",
        max_tokens=config.max_tokens,
        max_tool_rounds=config.max_tool_rounds,
        deadline_s=config.deadline_s,
    )


@dataclass(frozen=True)
class Citation:
    id: str
    kind: Literal["asset", "clause"]


@dataclass(frozen=True)
class ToolCall:
    """One tool call of a turn, with the result as the model was shown it (filtered)."""

    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass(frozen=True)
class Step:
    """One step of a turn as it happens, so the UI can show the copilot's progress: a generation
    step (an attempt starts, is validated or rejected, the provider failed, the template takes
    over) or a tool call with its arguments. A step never carries answer text: an answer is shown
    only once it has passed validation (or is the template's)."""

    kind: Literal[
        "attempt", "validating", "validated", "rejected", "failed", "fallback", "tool_call"
    ]
    attempt: int
    provider: str
    problems: tuple[str, ...] = ()
    reason: str | None = None
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


StepObserver = Callable[[Step], None]


@dataclass(frozen=True)
class CopilotAnswer:
    """The answer and how it was reached: what the "how I got this" panel shows."""

    text: str
    citations: list[Citation]
    provider: str
    fallback: bool
    tools_used: list[str]
    tool_calls: list[ToolCall]  # what the answering turn called and was shown (the eval reads it)
    advisory: int | None  # the advisory the tools answered about: the current one
    model: str | None  # the model of the answering turn; None for the template
    prompt_version: str | None
    attempts: list[dict[str, Any]]  # the attempt log, as audited
    fallback_reason: str | None

    @property
    def validated(self) -> bool:
        """Whether the answer shown passed the validator (the fallback template is not checked:
        it is deterministic and built from the same tools)."""
        return not self.fallback

    @property
    def tokens(self) -> tuple[int, int]:
        """Input and output tokens over every attempt of the turn."""
        usages = [a.get("usage", {}) for a in self.attempts]
        return (
            sum(u.get("input_tokens", 0) for u in usages),
            sum(u.get("output_tokens", 0) for u in usages),
        )


class _Recorder:
    """Runs tools for the provider and remembers the IDs they returned: asset and clause IDs,
    which become citations, and every ID anywhere in what a tool returned (an error that names
    an unknown asset included), which an answer may name: what the model is shown is citable.
    Every result passes the data classification filter first, so a restricted field never
    reaches the model and an ID only a restricted field held is not citable (CR-03 C1)."""

    def __init__(self, tools: CopilotTools, on_call: Callable[[str, dict[str, Any]], None]) -> None:
        self._tools = tools
        self._on_call = on_call
        self.asset_ids: set[str] = set()
        self.clause_ids: set[str] = set()
        self.other_ids: set[str] = set()
        self.calls: list[ToolCall] = []

    def __call__(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self._on_call(name, args)
        shown = self._run(name, args)
        self.calls.append(ToolCall(name, args, shown))
        return shown

    def _run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            output: ToolOutput = self._tools.run(name, args)
        except ToolError as error:
            return self._shown({"error": str(error)})[0]
        except TypeError:
            return {"error": f"wrong arguments for {name}"}
        shown, ids = self._shown(output.data)
        self.asset_ids |= output.asset_ids & ids
        self.clause_ids |= output.clause_ids
        return shown

    def _shown(self, data: dict[str, Any]) -> tuple[dict[str, Any], frozenset[str]]:
        """The filtered data and every ID in it, all of which an answer may name."""
        shown = for_model(data)
        text = json.dumps(shown, default=str)
        ids = mentioned(ENTITY_ID, text) | mentioned(CLAUSE_ID, text)
        self.other_ids |= ids
        return shown, ids


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
    """The copilot's validator: an answer names only IDs and states only numbers its tools
    returned, and is not empty. The number rule is `muster.numbers`, which the evaluation shares."""
    text = answered.chat.text
    _, ungrounded = _cite(text, answered.recorder)
    problems = ["it names IDs no tool returned: " + ", ".join(ungrounded)] if ungrounded else []
    results = [call.result for call in answered.recorder.calls]
    invented = ungrounded_numbers(text, results)
    problems += ["it states numbers no tool returned: " + ", ".join(invented)] if invented else []
    return problems + ([] if text else ["it has no text"])


def answer(
    session: Session,
    playbook: Playbook,
    provider: LLMProvider,
    question: str,
    history: list[ChatTurn],
    scoring: ScoringConfig,
    prompt: Prompt | None = None,
    on_step: StepObserver | None = None,
) -> CopilotAnswer:
    """`prompt` replaces the copilot prompt (the evaluation tries a candidate prompt with it).
    `on_step` is told each step of the turn as it happens (the streamed progress)."""
    config = scoring.copilot
    tools = CopilotTools(session, playbook, config)
    recent = history[-config.history_turns :]
    step = on_step or (lambda _: None)
    now = GenerationEvent("attempt", 1, provider.name)  # the step a tool call belongs to

    def observe(event: GenerationEvent) -> None:
        nonlocal now
        now = event
        step(Step(event.kind, event.attempt, event.provider, event.problems, event.reason))

    def called(name: str, args: dict[str, Any]) -> None:
        step(Step("tool_call", now.attempt, now.provider, tool=name, args=dict(args)))

    def ask(p: LLMProvider, prompt: Prompt, feedback: list[str]) -> _Answered:
        recorder = _Recorder(tools, called)  # each call is checked against the tools it ran
        asked = question + (_REJECTED + "\n- ".join(feedback) if feedback else "")
        return _Answered(p.chat(asked, recent, TOOL_DEFINITIONS, recorder, prompt), recorder)

    outcome = generate(
        provider,
        TemplateProvider.from_config(scoring),
        prompt or copilot_prompt(config),
        ask,
        _problems,
        1 + config.retries,
        rejected="the answer was not grounded",
        task="copilot",
        observe=observe,
    )
    result, recorder = outcome.result.chat, outcome.result.recorder
    citations, _ = _cite(result.text, recorder)

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
        result.text,
        citations,
        outcome.provider,
        outcome.fallback,
        result.tools_used,
        recorder.calls,
        advisory.advisory_no if advisory else None,
        result.model,
        outcome.prompt_version,
        outcome.attempts,
        outcome.fallback_reason,
    )
