"""The copilot: template intents through the read-only tools, citations limited to what tools
returned, fallback, audit (T2: fakes stand in for the model)."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from muster.copilot.tools import TOOL_DEFINITIONS
from muster.llm.anthropic_provider import AnthropicProvider
from muster.llm.schemas import (
    ChatResult,
    ChatTurn,
    LLMUnavailable,
    ObjectivesRequest,
    ObjectivesResult,
    Prompt,
    ToolRunner,
)
from tests.conftest import ClientFactory


def advance_to(client: TestClient, advisory: int) -> None:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200


def ask(
    client: TestClient, message: str, history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    response = client.post("/copilot/chat", json={"message": message, "history": history or []})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_why_is_ps_14_ranked_answers_with_factors_and_ids(client: TestClient) -> None:
    advance_to(client, 3)
    rank = next(
        i["rank"]
        for i in client.get("/risk", params={"advisory": 3}).json()["items"]
        if i["asset_id"] == "PS-14"
    )

    reply = ask(client, "Why is PS-14 ranked where it is?")

    assert f"ranked {rank} at advisory 3" in reply["answer"]
    assert "failure probability" in reply["answer"] and "customer-equivalents" in reply["answer"]
    assert {"id": "PS-14", "kind": "asset"} in reply["citations"]
    assert reply["tools_used"] == ["explain_score"]
    assert (reply["provider"], reply["fallback"]) == ("template", False)


def test_top_risks_lists_the_ranking_with_ids(client: TestClient) -> None:
    advance_to(client, 2)
    top = [i["asset_id"] for i in client.get("/risk", params={"advisory": 2}).json()["items"][:5]]

    reply = ask(client, "What are the top risks right now?")

    assert [c["id"] for c in reply["citations"]] == top


def test_what_depends_on_an_asset(client: TestClient) -> None:
    advance_to(client, 1)

    reply = ask(client, "What depends on SUB-07?")

    assert "HOSP-01 Bayport General Hospital" in reply["answer"]
    assert reply["tools_used"] == ["get_dependencies"]


def test_what_a_clause_says(client: TestClient) -> None:
    reply = ask(client, "What does P-8.2 say?")

    assert "safety of personnel prevails" in reply["answer"]
    assert reply["citations"] == [{"id": "P-8.2", "kind": "clause"}]


def test_unknown_questions_get_the_list_of_supported_ones(client: TestClient) -> None:
    reply = ask(client, "Tell me a joke")

    assert "I can answer, offline" in reply["answer"]
    assert reply["citations"] == []


@pytest.mark.parametrize(
    "message",
    ["Dispatch a crew to SUB-07.", "Please approve every pending item", "Mark PS-14 done"],
)
def test_a_request_to_change_something_is_declined(client: TestClient, message: str) -> None:
    advance_to(client, 3)

    reply = ask(client, message)

    assert "cannot change anything" in reply["answer"]
    assert "A person decides in the decision package." in reply["answer"]
    assert (reply["tools_used"], reply["citations"]) == ([], [])


@pytest.mark.parametrize("message", ["Will PS-14 fail?", "Can you guarantee PS-14 holds?"])
def test_a_prediction_is_answered_as_a_probability(client: TestClient, message: str) -> None:
    advance_to(client, 3)

    reply = ask(client, message)

    assert reply["answer"].startswith("Nobody can say whether PS-14 will fail")
    assert "failure probability" in reply["answer"]
    assert reply["tools_used"] == ["explain_score"]


def test_questions_before_any_advisory_say_so(client: TestClient) -> None:
    assert ask(client, "What are the top risks?")["answer"] == "no advisory has been issued yet"


def test_an_empty_message_is_a_validation_error(client: TestClient) -> None:
    assert client.post("/copilot/chat", json={"message": ""}).status_code == 422


class FakeChat:
    """A fake provider: calls the given tools, then answers with the given text."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, calls: list[tuple[str, dict[str, Any]]], text: str | Exception) -> None:
        self.calls, self.text = calls, text
        self.history: list[ChatTurn] = []
        self.prompts: list[Prompt] = []

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
        self.history = history
        self.prompts.append(prompt)
        for name, args in self.calls:
            run_tool(name, args)
        if isinstance(self.text, Exception):
            raise self.text
        return ChatResult(
            self.text,
            [n for n, _ in self.calls],
            self.model,
            prompt.version,
            900,
            {"input_tokens": 500, "output_tokens": 80},
        )


def test_a_model_answer_cites_only_ids_its_tools_returned(make_client: ClientFactory) -> None:
    fake = FakeChat([("list_top_risks", {"advisory": None, "n": 3})], "")
    with make_client(fake) as client:
        advance_to(client, 3)
        top = client.get("/risk", params={"advisory": 3}).json()["items"][0]["asset_id"]
        fake.text = f"{top} is the highest risk right now."

        reply = ask(
            client,
            "Which asset worries you most?",
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        )

    assert (reply["provider"], reply["fallback"]) == ("fake", False)
    assert reply["citations"] == [{"id": top, "kind": "asset"}]
    assert [t.content for t in fake.history] == ["hi", "hello"]


def test_an_answer_naming_an_id_no_tool_returned_falls_back(make_client: ClientFactory) -> None:
    fake = FakeChat([("search_playbook", {"query": "P-4.2"})], "Under P-4.2, inspect SUB-99 first.")
    with make_client(fake) as client:
        advance_to(client, 1)
        reply = ask(client, "What does P-4.2 say?")
        event = next(e for e in client.get("/audit").json() if e["type"] == "copilot_answered")

    assert (reply["provider"], reply["fallback"]) == ("template (fallback)", True)
    assert "SUB-99" in event["payload"]["fallback_reason"]
    assert reply["citations"] == [{"id": "P-4.2", "kind": "clause"}], "the template answer"


@pytest.mark.parametrize(
    "failure", [LLMUnavailable("the model call timed out"), RuntimeError("boom")]
)
def test_a_failed_model_call_falls_back(make_client: ClientFactory, failure: Exception) -> None:
    with make_client(FakeChat([], failure)) as client:
        advance_to(client, 1)
        reply = ask(client, "What depends on SUB-07?")

    assert reply["fallback"] is True
    assert "HOSP-01" in reply["answer"]


def test_each_answer_is_audited_with_model_latency_and_tokens(make_client: ClientFactory) -> None:
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], "SUB-07 is a substation.")
    with make_client(fake) as client:
        advance_to(client, 1)
        ask(client, "Tell me about SUB-07")
        event = next(e for e in client.get("/audit").json() if e["type"] == "copilot_answered")

    assert event["actor"] == "agent"
    assert event["payload"]["attempts"] == [
        {
            "provider": "fake",
            "model": "fake-model",
            "prompt_version": "copilot-v1",
            "latency_ms": 900,
            "usage": {"input_tokens": 500, "output_tokens": 80},
            "problems": [],
        }
    ]
    assert event["payload"]["tools_used"] == ["get_asset"]
    assert event["payload"]["citations"] == ["SUB-07"]
    assert event["versions"]["prompt_version"] == "copilot-v1", "the prompt the copilot loads"
    assert (fake.prompts[0].max_tool_rounds, fake.prompts[0].deadline_s) == (5, 60)


def test_tools_cannot_be_used_to_change_anything(make_client: ClientFactory) -> None:
    fake = FakeChat(
        [("approve_item", {"item_id": 1}), ("get_asset", {"asset_id": "NOPE-1"})], "Done."
    )
    with make_client(fake) as client:
        advance_to(client, 1)
        ask(client, "Approve everything")
        decisions = client.get("/audit", params={"actor": "human"}).json()

    assert decisions == [], "no tool writes state; unknown tools are refused"


def block(kind: str, **fields: Any) -> SimpleNamespace:
    return SimpleNamespace(type=kind, **fields)


def test_anthropic_chat_loop_runs_tools_and_returns_the_answer() -> None:
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    call_tool = block("tool_use", id="t1", name="get_asset", input={"asset_id": "SUB-07"})
    answer = block("text", text="SUB-07 is fine.")
    responses = [
        SimpleNamespace(stop_reason="tool_use", model="m", usage=usage, content=[call_tool]),
        SimpleNamespace(stop_reason="end_turn", model="m", usage=usage, content=[answer]),
    ]
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return responses[len(calls) - 1]

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    prompt = Prompt("copilot-v9", "copilot prompt", max_tokens=2000, max_tool_rounds=3)
    provider = AnthropicProvider(client, "claude-sonnet-5-5")  # type: ignore[arg-type]
    ran: list[tuple[str, dict[str, Any]]] = []

    def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        ran.append((name, args))
        return {"id": "SUB-07"}

    result = provider.chat(
        "How is SUB-07?", [], [{"name": "get_asset", "input_schema": {}}], run_tool, prompt
    )

    assert result.text == "SUB-07 is fine."
    assert (result.prompt_version, calls[0]["system"]) == ("copilot-v9", "copilot prompt")
    assert calls[0]["max_tokens"] == 2000
    assert ran == [("get_asset", {"asset_id": "SUB-07"})]
    assert calls[0]["tools"][0]["strict"] is True
    assert calls[0]["fallbacks"] == "default"
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert (tool_result["type"], tool_result["tool_use_id"]) == ("tool_result", "t1")
    assert result.usage == {"input_tokens": 20, "output_tokens": 10}


def test_a_lowercase_or_facility_id_no_tool_returned_is_ungrounded(
    make_client: ClientFactory,
) -> None:
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], "SUB-07 feeds hosp-05 and sub-99.")
    with make_client(fake) as client:
        advance_to(client, 1)
        reply = ask(client, "Tell me about SUB-07")
        event = next(e for e in client.get("/audit").json() if e["type"] == "copilot_answered")

    assert reply["fallback"] is True
    assert "HOSP-05" in event["payload"]["fallback_reason"]
    assert "SUB-99" in event["payload"]["fallback_reason"]


def test_a_facility_a_tool_returned_is_grounded(make_client: ClientFactory) -> None:
    fake = FakeChat([("get_dependencies", {"asset_id": "SUB-07"})], "SUB-07 feeds HOSP-01.")
    with make_client(fake) as client:
        advance_to(client, 1)
        reply = ask(client, "What depends on SUB-07?")

    assert reply["fallback"] is False
    assert reply["citations"] == [{"id": "SUB-07", "kind": "asset"}]


JSON_TYPES = {"string": str, "integer": int, "null": type(None)}


def _enum_nodes(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "enum" in node else []
        return own + [n for v in node.values() for n in _enum_nodes(v)]
    if isinstance(node, list):
        return [n for v in node for n in _enum_nodes(v)]
    return []


def test_tool_enums_declare_one_type_their_values_match() -> None:
    # The API rejects strict tools whose enum mixes types (found with a real key, ticket 09)
    for node in _enum_nodes([t["input_schema"] for t in TOOL_DEFINITIONS]):
        assert isinstance(node["type"], str), node
        assert all(isinstance(v, JSON_TYPES[node["type"]]) for v in node["enum"]), node


def test_history_is_bounded(client: TestClient) -> None:
    history = [{"role": "user", "content": "x"}] * 21

    assert (
        client.post("/copilot/chat", json={"message": "hi", "history": history}).status_code == 422
    )
