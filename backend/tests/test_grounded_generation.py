"""Grounded generation for the situation report: the configured provider's draft is used only if
the draft request validator accepts it; otherwise it is retried, then the template serves the
fallback (L9). Requests are built by hand and the provider is an honest fake (T2)."""

from dataclasses import replace
from typing import Any

from app.agent.draft import produce_draft
from app.config import REPO_ROOT
from app.llm.grounded import FALLBACK_LABEL
from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftItem,
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    Paragraph,
    Section,
    SitrepDraft,
    ToolRunner,
    TopAsset,
)
from app.llm.template import TemplateProvider
from app.replay.diff import AdvisoryChanges
from app.scoring_config import load_scoring_config

TEMPLATE = TemplateProvider(top_risks=5, top_assets=3)
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
    prompt_version: str | None = "fake-prompt-v1"

    def __init__(self, *outputs: SitrepDraft | Exception) -> None:
        self.outputs = list(outputs)
        self.feedback: list[list[str]] = []

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        self.feedback.append(request.feedback)
        output = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(output, Exception):
            raise output
        return DraftResult(output, self.name, self.model, 7, {"input_tokens": 3})

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
    ) -> ChatResult:
        raise LLMUnavailable("not used here")


def test_a_valid_first_attempt_is_used() -> None:
    outcome = produce_draft(FakeProvider(GROUNDED), TEMPLATE, REQUEST, attempts=2)

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

    outcome = produce_draft(fake, TEMPLATE, REQUEST, attempts=2)

    assert (outcome.result.draft, outcome.fallback) == (GROUNDED, False)
    assert fake.feedback[0] == []
    assert any("P-9.9" in problem for problem in fake.feedback[1])
    assert [bool(a["problems"]) for a in outcome.attempts] == [True, False]


def test_exhausted_attempts_fall_back_to_the_template_with_the_fallback_label() -> None:
    outcome = produce_draft(FakeProvider(INVENTED), TEMPLATE, REQUEST, attempts=3)

    assert (outcome.provider, outcome.fallback) == (FALLBACK_LABEL, True)
    assert outcome.provider == "template (fallback)"
    assert outcome.result.draft == TEMPLATE.draft_sitrep(REQUEST).draft
    assert outcome.prompt_version is None
    assert len(outcome.attempts) == 3
    assert outcome.fallback_reason is not None and "P-9.9" in outcome.fallback_reason


def test_a_raising_provider_falls_back_without_retrying() -> None:
    fake = FakeProvider(LLMUnavailable("the model call timed out"))

    outcome = produce_draft(fake, TEMPLATE, REQUEST, attempts=3)

    assert (outcome.provider, outcome.fallback) == (FALLBACK_LABEL, True)
    assert outcome.fallback_reason == "the model call timed out"
    assert len(outcome.attempts) == 1 and "latency_ms" in outcome.attempts[0]


def test_an_unexpected_provider_error_is_not_shown() -> None:
    outcome = produce_draft(FakeProvider(RuntimeError("secret detail")), TEMPLATE, REQUEST, 2)

    assert outcome.fallback_reason == "unexpected provider error"
    assert outcome.attempts[0]["error"] == "unexpected provider error"


def test_a_configured_template_is_not_labelled_a_fallback() -> None:
    outcome = produce_draft(TEMPLATE, TEMPLATE, REQUEST, attempts=2)

    assert (outcome.provider, outcome.fallback, outcome.fallback_reason) == (
        "template",
        False,
        None,
    )
    assert outcome.prompt_version is None


def test_the_fallback_template_uses_its_configured_settings() -> None:
    top = [TopAsset(f"SUB-0{n}", "substation", n, 0.5) for n in range(1, 6)]
    request = replace(REQUEST, items=[], top_assets=top)

    outcome = produce_draft(FakeProvider(INVENTED), TEMPLATE, request, attempts=1)

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

    draft = template.draft_sitrep(replace(REQUEST, items=[], top_assets=top)).draft
    template.chat("What are the top risks?", [], [], run_tool)

    named = {a for s in draft.sections for p in s.paragraphs for a in p.asset_ids}
    assert named == {"SUB-01", "SUB-02"}, "draft.template_top_assets"
    assert asked[0]["n"] == 4, "copilot.top_risks_default"
