"""The draft situation report: providers, citation validation, fallback, approval (T2: no real
LLM; fakes stand in behind the provider interface)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.llm.anthropic_provider import AnthropicProvider, CopilotPrompt
from app.llm.factory import LLMConfigError, build_provider
from app.llm.schemas import (
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    Paragraph,
    Section,
    SitrepDraft,
)
from app.main import create_app
from app.scoring_config import load_scoring_config
from tests.conftest import ClientFactory


def advance_to(client: TestClient, advisory: int) -> None:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200


def package(client: TestClient, advisory: int) -> dict[str, Any]:
    result: dict[str, Any] = client.get(f"/packages/{advisory}").json()
    return result


def draft_of(*paragraphs: Paragraph) -> SitrepDraft:
    return SitrepDraft(sections=[Section(heading="Situation", paragraphs=list(paragraphs))])


class FakeProvider:
    """Returns the given drafts in turn (or raises), and records what it was shown."""

    name = "anthropic"
    model: str | None = "claude-sonnet-5-5"
    prompt_version: str | None = "sitrep-v1"

    def __init__(self, *outputs: SitrepDraft | Exception) -> None:
        self.outputs = list(outputs)
        self.requests: list[DraftRequest] = []

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        self.requests.append(request)
        output = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(output, Exception):
            raise output
        return DraftResult(
            output, "anthropic", "claude-sonnet-5-5", 42, {"input_tokens": 100, "output_tokens": 50}
        )


def drafted_event(client: TestClient) -> dict[str, Any]:
    return next(e for e in client.get("/audit").json() if e["type"] == "sitrep_drafted")


def test_template_draft_is_marked_draft_and_cites_only_grounded_ids(client: TestClient) -> None:
    advance_to(client, 3)

    draft = package(client, 3)["draft"]

    assert (draft["status"], draft["provider"], draft["fallback_reason"]) == (
        "DRAFT",
        "template",
        None,
    )
    paragraphs = [p for s in draft["sections"] for p in s["paragraphs"]]
    assert any("P-4.5" in p["clause_ids"] and "SUB-07" in p["asset_ids"] for p in paragraphs)
    assert drafted_event(client)["payload"]["clauses_retrieved"], "BM25 found context clauses"


def test_a_grounded_llm_draft_is_used_and_its_call_is_logged(make_client: ClientFactory) -> None:
    fake = FakeProvider(
        draft_of(
            Paragraph(
                text="SUB-07 needs a generator (P-4.5).", clause_ids=["P-4.5"], asset_ids=["SUB-07"]
            )
        )
    )
    with make_client(fake) as client:
        advance_to(client, 3)

        draft = package(client, 3)["draft"]
        assert (draft["provider"], draft["model"]) == ("anthropic", "claude-sonnet-5-5")
        attempt = drafted_event(client)["payload"]["attempts"][0]
        assert attempt["usage"] == {"input_tokens": 100, "output_tokens": 50}
        assert attempt["latency_ms"] == 42


def test_an_invented_clause_is_rejected_and_the_template_draft_served(
    make_client: ClientFactory,
) -> None:
    invented = draft_of(
        Paragraph(text="Apply P-9.9 at SUB-07.", clause_ids=["P-9.9"], asset_ids=["SUB-07"])
    )
    with make_client(FakeProvider(invented)) as client:
        advance_to(client, 3)

        draft = package(client, 3)["draft"]
        assert draft["provider"] == "template (fallback)"
        assert "P-9.9" in draft["fallback_reason"]
        attempts = drafted_event(client)["payload"]["attempts"]
        assert len(attempts) == 2, "one retry before falling back"


def test_an_id_in_the_text_must_be_listed(make_client: ClientFactory) -> None:
    unlisted = draft_of(
        Paragraph(text="PS-14 is at risk under P-4.2.", clause_ids=[], asset_ids=[])
    )
    fixed = draft_of(
        Paragraph(text="PS-14 is at risk under P-4.2.", clause_ids=["P-4.2"], asset_ids=["PS-14"])
    )
    fake = FakeProvider(unlisted, fixed)
    with make_client(fake) as client:
        advance_to(client, 3)

        assert package(client, 3)["draft"]["provider"] == "anthropic", "the retry fixed it"
        assert any("PS-14" in problem for problem in fake.requests[1].feedback)


def test_a_failed_call_falls_back_to_the_template(make_client: ClientFactory) -> None:
    with make_client(FakeProvider(LLMUnavailable("the model call timed out"))) as client:
        advance_to(client, 1)

        draft = package(client, 1)["draft"]
        assert draft["provider"] == "template (fallback)"
        assert draft["fallback_reason"] == "the model call timed out"


def test_the_provider_sees_plain_data_and_writes_no_state(make_client: ClientFactory) -> None:
    fake = FakeProvider(draft_of(Paragraph(text="Quiet advisory.", clause_ids=[], asset_ids=[])))
    with make_client(fake) as client:
        advance_to(client, 1)

        request = fake.requests[0]
        assert isinstance(request, DraftRequest)
        assert not any(hasattr(v, "exec") for v in vars(request).values()), "no database session"
        assert request.items and request.clauses
        states = [e for e in client.get("/audit").json() if e["payload"].get("state_written")]
        assert states == [], "nothing but a person's decision writes operational state"


def test_the_commander_edits_and_approves_and_p_7_1_is_satisfied(client: TestClient) -> None:
    advance_to(client, 1)
    text = package(client, 1)["draft_text"] + "\n\nCrews briefed at 06:00."

    refused = client.post("/sitrep/1/approve", json={"role": "planning", "text": text})
    approved = client.post("/sitrep/1/approve", json={"role": "director", "text": text})

    assert refused.status_code == 403
    assert approved.status_code == 200
    assert approved.json()["edited"] is True
    findings = client.get("/findings", params={"advisory": 1}).json()
    assert next(f for f in findings if f["rule_id"] == "P-7.1")["status"] == "satisfied"
    assert package(client, 1)["sitrep"]["approved_by"] == "director"
    event = next(e for e in client.get("/audit").json() if e["type"] == "sitrep_approved")
    assert event["actor"] == "human" and event["payload"]["edited"] is True


def test_approving_the_draft_unchanged_is_not_an_edit_and_holds_one_period(
    client: TestClient,
) -> None:
    advance_to(client, 1)
    approved = client.post(
        "/sitrep/1/approve", json={"role": "director", "text": package(client, 1)["draft_text"]}
    )
    again = client.post("/sitrep/1/approve", json={"role": "director", "text": "x"})

    advance_to(client, 2)

    assert approved.json()["edited"] is False
    assert again.status_code == 409
    findings = client.get("/findings", params={"advisory": 2}).json()
    assert next(f for f in findings if f["rule_id"] == "P-7.1")["status"] == "open"
    assert (
        client.post("/sitrep/1/approve", json={"role": "director", "text": "late"}).status_code
        == 409
    )


def test_anthropic_without_a_key_fails_at_startup(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key=None,
        database_path=tmp_path / "db.sqlite",
    )  # type: ignore[call-arg]

    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY"), TestClient(create_app(settings)):
        pass


def test_template_needs_no_key() -> None:
    config = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
    assert build_provider(Settings(_env_file=None), config).name == "template"  # type: ignore[call-arg]


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error = response, error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def anthropic_with(messages: FakeMessages) -> AnthropicProvider:
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    copilot = CopilotPrompt(
        system="copilot prompt", version="copilot-v1", max_tokens=2000, max_tool_rounds=3
    )
    return AnthropicProvider(
        client,  # type: ignore[arg-type]  # a fake with the same beta.messages surface
        "claude-sonnet-5-5",
        "system prompt",
        "sitrep-v1",
        4000,
        copilot,
    )


def request() -> DraftRequest:
    return DraftRequest(1, 72, "prepare", {}, [], [], [])


def test_anthropic_provider_sends_findings_as_delimited_data_with_refusal_fallback() -> None:
    parsed = draft_of(Paragraph(text="ok", clause_ids=[], asset_ids=[]))
    response = SimpleNamespace(
        parsed_output=parsed, stop_reason="end_turn", model="claude-sonnet-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )  # fmt: skip
    messages = FakeMessages(response)

    result = anthropic_with(messages).draft_sitrep(request())

    call = messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_format"] is SitrepDraft
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["messages"][0]["content"].startswith("<findings>")
    assert "temperature" not in call
    assert result.usage == {"input_tokens": 10, "output_tokens": 5}


def test_anthropic_refusal_and_errors_become_llm_unavailable() -> None:
    refusal = SimpleNamespace(
        parsed_output=None,
        stop_reason="refusal",
        model="m",
        usage=SimpleNamespace(input_tokens=1, output_tokens=0),
    )
    with pytest.raises(LLMUnavailable, match="declined"):
        anthropic_with(FakeMessages(refusal)).draft_sitrep(request())

    error = anthropic.APIConnectionError(request=None)  # type: ignore[arg-type]
    with pytest.raises(LLMUnavailable, match="reach"):
        anthropic_with(FakeMessages(error=error)).draft_sitrep(request())


def test_approving_a_report_for_an_advisory_not_issued_is_not_found(client: TestClient) -> None:
    response = client.post("/sitrep/1/approve", json={"role": "director", "text": "x"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_failed_call_records_latency_and_model(make_client: ClientFactory) -> None:
    with make_client(FakeProvider(LLMUnavailable("model provider error 503"))) as client:
        advance_to(client, 1)
        attempt = drafted_event(client)["payload"]["attempts"][0]

    assert attempt["error"] == "model provider error 503"
    assert attempt["model"] == "claude-sonnet-5-5"
    assert attempt["prompt_version"] == "sitrep-v1"
    assert "latency_ms" in attempt


def test_any_provider_failure_serves_the_template(make_client: ClientFactory) -> None:
    with make_client(FakeProvider(RuntimeError("boom"))) as client:
        advance_to(client, 1)
        draft = package(client, 1)["draft"]

    assert (draft["provider"], draft["fallback"]) == ("template (fallback)", True)
    assert draft["fallback_reason"] == "unexpected provider error"


def test_staging_area_ids_in_the_text_must_be_listed(make_client: ClientFactory) -> None:
    unlisted = draft_of(Paragraph(text="Move crews out of STG-02.", clause_ids=[], asset_ids=[]))
    with make_client(FakeProvider(unlisted)) as client:
        advance_to(client, 4)
        draft = package(client, 4)["draft"]

    assert "STG-02" in draft["fallback_reason"]
    template_paragraphs = [p for s in draft["sections"] for p in s["paragraphs"]]
    assert any("STG-02" in p["asset_ids"] for p in template_paragraphs)
