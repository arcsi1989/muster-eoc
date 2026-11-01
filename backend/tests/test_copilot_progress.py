"""The copilot shows its work: each step of a turn is told as it happens (tool calls, validation,
retries, the template fallback), no step carries answer text, and the answer keeps what the
"how I got this" panel shows. Seeded session and an honest fake provider (T2)."""

from typing import Any

import pytest

from muster.copilot.chat import CopilotAnswer, Step, StepObserver, answer, stream_answer
from muster.errors import DataNotLoaded
from muster.llm.grounded import FALLBACK_LABEL
from muster.llm.schemas import (
    ChatResult,
    ChatTurn,
    LLMUnavailable,
    ObjectivesRequest,
    ObjectivesResult,
    Prompt,
    ToolRunner,
)
from muster.llm.template import TemplateProvider
from tests.conftest import SeededScenario


class FakeChat:
    """Calls get_asset for SUB-07, then answers with the given texts in turn (or raises)."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, *texts: str | Exception) -> None:
        self.texts = list(texts)

    def draft_sitrep(self, request: Any, prompt: Prompt) -> Any:
        raise LLMUnavailable("not used here")

    def rephrase_objectives(self, request: ObjectivesRequest, prompt: Prompt) -> ObjectivesResult:
        raise LLMUnavailable("not used here")

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult:
        run_tool("get_asset", {"asset_id": "SUB-07"})
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        if isinstance(text, Exception):
            raise text
        usage = {"input_tokens": 400, "output_tokens": 50}
        return ChatResult(text, ["get_asset"], self.model, prompt.version, 9, usage)


def run(
    seeded: SeededScenario, provider: Any, retries: int = 0
) -> tuple[CopilotAnswer, list[Step]]:
    seeded.issue_until(2)
    scoring = seeded.scoring.model_copy(
        update={"copilot": seeded.scoring.copilot.model_copy(update={"retries": retries})}
    )
    steps: list[Step] = []
    reply = answer(
        seeded.session,
        seeded.playbook,
        provider,
        "How is SUB-07?",
        [],
        scoring,
        on_step=steps.append,
    )
    return reply, steps


def kinds(steps: list[Step]) -> list[tuple[str, int, str]]:
    return [(s.kind, s.attempt, s.tool or s.provider) for s in steps]


def test_a_grounded_answer_reports_its_tool_call_and_validation(seeded: SeededScenario) -> None:
    reply, steps = run(seeded, FakeChat("SUB-07 is a substation."))

    assert kinds(steps) == [
        ("attempt", 1, "fake"),
        ("tool_call", 1, "get_asset"),
        ("validating", 1, "fake"),
        ("validated", 1, "fake"),
    ]
    assert steps[1].args == {"asset_id": "SUB-07"}
    assert reply.validated and not reply.fallback


def test_a_rejected_answer_reports_the_problems_and_the_retry(seeded: SeededScenario) -> None:
    _, steps = run(seeded, FakeChat("SUB-99 is fine.", "SUB-07 is fine."), retries=1)

    assert [(s.kind, s.attempt) for s in steps if s.kind != "tool_call"] == [
        ("attempt", 1),
        ("validating", 1),
        ("rejected", 1),
        ("attempt", 2),
        ("validating", 2),
        ("validated", 2),
    ]
    rejected = next(s for s in steps if s.kind == "rejected")
    assert rejected.problems == ("it names IDs no tool returned: SUB-99",)


def test_a_failed_provider_reports_the_fallback_and_the_templates_tools(
    seeded: SeededScenario,
) -> None:
    reply, steps = run(seeded, FakeChat(LLMUnavailable("the model call timed out")))

    assert kinds(steps) == [
        ("attempt", 1, "fake"),
        ("tool_call", 1, "get_asset"),
        ("failed", 1, "fake"),
        ("fallback", 1, FALLBACK_LABEL),
        ("tool_call", 1, "explain_score"),
    ]
    assert steps[3].reason == "the model call timed out"
    assert (reply.provider, reply.fallback, reply.validated) == (FALLBACK_LABEL, True, False)


def test_no_step_carries_answer_text(seeded: SeededScenario) -> None:
    rejected, accepted = "SUB-07 feeds SUB-99 and more.", "SUB-07 is a quiet substation."
    reply, steps = run(seeded, FakeChat(rejected, accepted), retries=1)

    shown = repr(steps)
    assert reply.text == accepted
    assert accepted not in shown and rejected not in shown


def test_the_answer_keeps_how_it_got_there(seeded: SeededScenario) -> None:
    reply, _ = run(seeded, FakeChat("SUB-99 is fine.", "SUB-07 is fine."), retries=1)

    assert reply.advisory == 2
    assert (reply.model, reply.prompt_version) == ("fake-model", "copilot-v2")
    assert [bool(a["problems"]) for a in reply.attempts] == [True, False]
    assert reply.tokens == (800, 100), "both attempts' tokens"
    assert [(c.name, c.args) for c in reply.tool_calls] == [("get_asset", {"asset_id": "SUB-07"})]
    assert reply.tool_calls[0].result["id"] == "SUB-07", "the result as the model saw it"


def test_the_configured_template_answers_with_the_same_steps_offline(
    seeded: SeededScenario,
) -> None:
    reply, steps = run(seeded, TemplateProvider.from_config(seeded.scoring))

    assert kinds(steps) == [
        ("attempt", 1, "template"),
        ("tool_call", 1, "explain_score"),
        ("validating", 1, "template"),
        ("validated", 1, "template"),
    ]
    assert (reply.provider, reply.validated, reply.tokens, reply.model) == (
        "template",
        True,
        (0, 0),
        None,
    )


def test_a_streamed_turn_yields_its_steps_as_they_happen_then_the_answer(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(1)
    template = TemplateProvider.from_config(seeded.scoring)

    def turn(on_step: StepObserver) -> CopilotAnswer:
        return answer(
            seeded.session, seeded.playbook, template, "What depends on SUB-07?", [],
            seeded.scoring, on_step=on_step,
        )  # fmt: skip

    items = list(stream_answer(turn))

    assert [i.kind for i in items[:-1] if isinstance(i, Step)] == [
        "attempt", "tool_call", "validating", "validated",
    ]  # fmt: skip
    assert isinstance(items[-1], CopilotAnswer) and "HOSP-01" in items[-1].text


def test_a_streamed_turn_raises_its_error_after_the_steps_before_it() -> None:
    def turn(on_step: StepObserver) -> CopilotAnswer:
        on_step(Step("attempt", 1, "fake"))
        raise DataNotLoaded("scenario state missing")

    received: list[Step | CopilotAnswer] = []
    with pytest.raises(DataNotLoaded):
        for item in stream_answer(turn):
            received.append(item)

    assert received == [Step("attempt", 1, "fake")]
