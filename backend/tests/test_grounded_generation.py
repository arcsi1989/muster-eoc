"""Grounded generation for the situation report and the copilot: the configured provider's result
is used only if the task's validator accepts it; otherwise it is retried, then the template
serves the fallback (L9). Requests are built by hand or come from the seeded session, and the
provider is an honest fake (T2)."""

from dataclasses import replace
from typing import Any

from sqlmodel import select

from muster.agent.draft import produce_draft
from muster.config import REPO_ROOT
from muster.copilot.chat import answer
from muster.llm.grounded import FALLBACK_LABEL
from muster.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftItem,
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    ObjectivesRequest,
    ObjectivesResult,
    Paragraph,
    Prompt,
    Section,
    SitrepDraft,
    ToolRunner,
    TopAsset,
)
from muster.llm.template import TemplateProvider
from muster.models import AuditEvent
from muster.replay.diff import AdvisoryChanges
from muster.scoring_config import load_scoring_config
from tests.conftest import SeededScenario

TEMPLATE = TemplateProvider(top_risks=5, top_assets=3)
PROMPT = Prompt("fake-prompt-v1", "Write the report.", max_tokens=100)
REQUEST = DraftRequest(
    advisory_no=3,
    hours_to_landfall=48,
    activation_level="prepare",
    changes=AdvisoryChanges(advisory_no=3),
    items=[DraftItem("P-4.5", "PS-09", True, "gap", "Stage a generator", ["P-4.5"], False)],
    top_assets=[],
    clauses=[],
)
GROUNDED = SitrepDraft(
    sections=[
        Section(
            heading="Situation",
            paragraphs=[
                Paragraph(text="PS-09 (P-4.5).", clause_ids=["P-4.5"], asset_ids=["PS-09"])
            ],
        )
    ]
)
INVENTED = SitrepDraft(
    sections=[
        Section(
            heading="Situation",
            paragraphs=[Paragraph(text="Apply P-9.9.", clause_ids=["P-9.9"], asset_ids=[])],
        )
    ]
)


class FakeProvider:
    """A fake provider: returns the given drafts in turn (or raises them) and records the
    feedback each try was sent."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, *outputs: SitrepDraft | Exception) -> None:
        self.outputs = list(outputs)
        self.feedback: list[list[str]] = []

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        self.feedback.append(request.feedback)
        output = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(output, Exception):
            raise output
        return DraftResult(output, self.name, self.model, prompt.version, 7, {"input_tokens": 3})

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
        raise LLMUnavailable("not used here")


def test_a_valid_first_attempt_is_used() -> None:
    outcome = produce_draft(FakeProvider(GROUNDED), TEMPLATE, PROMPT, REQUEST, attempts=2)

    assert outcome.result.draft == GROUNDED
    assert (outcome.provider, outcome.fallback, outcome.fallback_reason) == ("fake", False, None)
    assert outcome.prompt_version == "fake-prompt-v1"
    assert outcome.attempts == [
        {
            "provider": "fake",
            "model": "fake-model",
            "prompt_version": "fake-prompt-v1",
            "latency_ms": 7,
            "usage": {"input_tokens": 3},
            "problems": [],
        }
    ]


def test_an_invalid_attempt_is_retried_with_its_problems_as_feedback() -> None:
    fake = FakeProvider(INVENTED, GROUNDED)

    outcome = produce_draft(fake, TEMPLATE, PROMPT, REQUEST, attempts=2)

    assert (outcome.result.draft, outcome.fallback) == (GROUNDED, False)
    assert fake.feedback[0] == []
    assert any("P-9.9" in problem for problem in fake.feedback[1])
    assert [bool(a["problems"]) for a in outcome.attempts] == [True, False]


def test_exhausted_attempts_fall_back_to_the_template_with_the_fallback_label() -> None:
    outcome = produce_draft(FakeProvider(INVENTED), TEMPLATE, PROMPT, REQUEST, attempts=3)

    assert (outcome.provider, outcome.fallback) == (FALLBACK_LABEL, True)
    assert outcome.provider == "template (fallback)"
    assert outcome.result.draft == TEMPLATE.draft_sitrep(REQUEST, PROMPT).draft
    assert outcome.prompt_version is None
    assert len(outcome.attempts) == 3
    assert outcome.fallback_reason is not None and "P-9.9" in outcome.fallback_reason


def test_a_raising_provider_falls_back_without_retrying() -> None:
    fake = FakeProvider(LLMUnavailable("the model call timed out"))

    outcome = produce_draft(fake, TEMPLATE, PROMPT, REQUEST, attempts=3)

    assert (outcome.provider, outcome.fallback) == (FALLBACK_LABEL, True)
    assert outcome.fallback_reason == "the model call timed out"
    assert len(outcome.attempts) == 1 and "latency_ms" in outcome.attempts[0]


def test_an_unexpected_provider_error_is_not_shown() -> None:
    outcome = produce_draft(
        FakeProvider(RuntimeError("secret detail")), TEMPLATE, PROMPT, REQUEST, 2
    )

    assert outcome.fallback_reason == "unexpected provider error"
    assert outcome.attempts[0]["error"] == "unexpected provider error"


def test_a_configured_template_is_not_labelled_a_fallback() -> None:
    outcome = produce_draft(TEMPLATE, TEMPLATE, PROMPT, REQUEST, attempts=2)

    assert (outcome.provider, outcome.fallback, outcome.fallback_reason) == (
        "template",
        False,
        None,
    )
    assert outcome.prompt_version is None


def test_the_fallback_template_uses_its_configured_settings() -> None:
    top = [TopAsset(f"SUB-0{n}", "substation", n, 0.5) for n in range(1, 6)]
    request = replace(REQUEST, items=[], top_assets=top)

    outcome = produce_draft(FakeProvider(INVENTED), TEMPLATE, PROMPT, request, attempts=1)

    named = {a for s in outcome.result.draft.sections for p in s.paragraphs for a in p.asset_ids}
    assert named == {"SUB-01", "SUB-02", "SUB-03"}, "the template is configured to name three"


def test_the_template_reads_its_settings_from_configuration() -> None:
    config = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
    config = config.model_copy(
        update={
            "draft": config.draft.model_copy(update={"template_top_assets": 2}),
            "copilot": config.copilot.model_copy(update={"top_risks_default": 4}),
        }
    )
    template = TemplateProvider.from_config(config)
    top = [TopAsset(f"SUB-0{n}", "substation", n, 0.5) for n in range(1, 6)]
    asked: list[dict[str, Any]] = []

    def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        asked.append(args)
        return {"error": "not needed here"}

    draft = template.draft_sitrep(replace(REQUEST, items=[], top_assets=top), PROMPT).draft
    template.chat("What are the top risks?", [], [], run_tool, PROMPT)

    named = {a for s in draft.sections for p in s.paragraphs for a in p.asset_ids}
    assert named == {"SUB-01", "SUB-02"}, "draft.template_top_assets"
    assert asked[0]["n"] == 4, "copilot.top_risks_default"


class FakeChat:
    """A fake copilot provider: calls one tool, then answers with the given text."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.questions: list[str] = []

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
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
        self.questions.append(question)
        run_tool("get_asset", {"asset_id": "SUB-07"})
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return ChatResult(text, ["get_asset"], self.model, prompt.version, 5, {})


def test_the_attempt_log_has_the_same_format_for_both_tasks(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    sitrep = produce_draft(FakeProvider(GROUNDED), TEMPLATE, PROMPT, REQUEST, attempts=1)

    def chat_attempts(text: str) -> list[dict[str, Any]]:
        answer(
            seeded.session, seeded.playbook, FakeChat(text), "How is SUB-07?", [], seeded.scoring
        )
        events = seeded.session.exec(
            select(AuditEvent).where(AuditEvent.type == "copilot_answered")
        )
        attempts: list[dict[str, Any]] = events.all()[-1].payload["attempts"]
        return attempts

    grounded, ungrounded = chat_attempts("SUB-07 is fine."), chat_attempts("SUB-99 is fine.")

    assert set(grounded[0]) == set(ungrounded[0]) == set(sitrep.attempts[0])
    assert grounded[0]["prompt_version"] == "copilot-v2"
    assert ungrounded[0]["problems"] == ["it names IDs no tool returned: SUB-99"]


def test_a_configured_template_copilot_is_not_labelled_a_fallback(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    template = TemplateProvider.from_config(seeded.scoring)

    answers = [
        answer(seeded.session, seeded.playbook, template, question, [], seeded.scoring)
        for question in (
            "What depends on SUB-07?",
            "What does P-8.2 say?",
            "Tell me a joke",
            "Why is SUB-99 ranked where it is?",  # it names a shelter the tool returned
            "What depends on SUB-998?",
        )
    ]

    assert [(a.provider, a.fallback) for a in answers] == [("template", False)] * 5
    assert "SHEL-01" in answers[3].text
    assert answers[4].text == "unknown asset SUB-998" and answers[4].citations == []


def test_a_copilot_retry_is_sent_the_problems_when_configured(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    scoring = seeded.scoring.model_copy(
        update={"copilot": seeded.scoring.copilot.model_copy(update={"retries": 1})}
    )
    fake = FakeChat("SUB-99 is fine.", "SUB-07 is fine.")

    reply = answer(seeded.session, seeded.playbook, fake, "How is SUB-07?", [], scoring)

    assert (reply.provider, reply.fallback, reply.text) == ("fake", False, "SUB-07 is fine.")
    assert fake.questions[0] == "How is SUB-07?"
    assert "SUB-99" in fake.questions[1] and fake.questions[1].startswith("How is SUB-07?")


def test_an_invented_number_is_retried_then_served_by_the_template(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    scoring = seeded.scoring.model_copy(
        update={"copilot": seeded.scoring.copilot.model_copy(update={"retries": 1})}
    )
    fake = FakeChat("SUB-07 serves 9,999 customers.", "SUB-07 serves 8,000 customers.")

    reply = answer(seeded.session, seeded.playbook, fake, "How is SUB-07?", [], scoring)
    event = seeded.session.exec(
        select(AuditEvent).where(AuditEvent.type == "copilot_answered")
    ).all()[-1]

    assert (reply.provider, reply.fallback) == (FALLBACK_LABEL, True)
    assert "9,999" in fake.questions[1], "the retry is sent the problem"
    assert [a["problems"] for a in event.payload["attempts"]] == [
        ["it states numbers no tool returned: 9,999"],
        ["it states numbers no tool returned: 8,000"],
    ]
    assert "8,000" in event.payload["fallback_reason"]
