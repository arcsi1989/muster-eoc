"""The copilot: template intents through the read-only tools, citations limited to what tools
returned, fallback, audit (T2: fakes stand in for the model)."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from muster.api import routes_copilot
from muster.classification import RESTRICTED_KEYS
from muster.copilot.chat import Step
from muster.copilot.tools import TOOL_DEFINITIONS
from muster.errors import DataNotLoaded
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
from tests.test_classification import keys


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


def test_how_bad_and_where_answers_from_the_outage_forecast(client: TestClient) -> None:
    advance_to(client, 3)
    forecast = client.get("/forecast", params={"advisory": 3}).json()

    reply = ask(client, "How bad, where, and do we have enough crews?")

    assert reply["tools_used"] == ["get_outage_forecast"]
    assert (reply["provider"], reply["fallback"]) == ("template", False)  # every number grounded
    for d in forecast["districts"]:
        p50, p90 = round(d["power_customers"]["p50"]), round(d["power_customers"]["p90"])
        assert f"{d['district']}: {p50:,}–{p90:,} power" in reply["answer"]
    assert "A forecast, not a decision." in reply["answer"]


def test_the_outage_answer_names_the_crew_shortfall_the_tool_worked_out(
    client: TestClient,
) -> None:
    advance_to(client, 4)
    forecast = client.get("/forecast", params={"advisory": 4}).json()

    reply = ask(client, "How many customers out by district?")

    assert reply["citations"] == []  # districts and counts only: no asset or clause
    for d in forecast["districts"]:
        short = d["crews_short_p90"]
        assert (f"({short:,} short at P90)" in reply["answer"]) == bool(short), d["district"]


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("What are the top risks for generators?", "list_top_risks"),
        ("Which assets are most at risk, and do crews have enough time?", "list_top_risks"),
        ("How many customers out in Bayport West?", "get_outage_forecast"),
        ("Do we have enough crews?", "get_outage_forecast"),
        ("How many generators are needed?", "get_outage_forecast"),
        ("Where is the outage worst?", "get_outage_forecast"),
    ],
)
def test_the_template_routes_forecast_questions_and_only_those(
    client: TestClient, message: str, tool: str
) -> None:
    advance_to(client, 3)

    assert ask(client, message)["tools_used"] == [tool]


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


def test_correct_numbers_pass_the_runtime_validator(make_client: ClientFactory) -> None:
    fake = FakeChat(
        [("get_asset", {"asset_id": "SUB-07"}), ("list_top_risks", {"advisory": None, "n": 1})], ""
    )
    with make_client(fake) as client:
        advance_to(client, 3)
        top = client.get("/risk", params={"advisory": 3}).json()["items"][0]
        percent = int(top["p_fail"] * 100 + 0.5)  # half-up, as a person writes it
        fake.text = (
            f"SUB-07 serves 4,400 customers (4400), 5.8km from the coast, about 6 km; installed "
            f"in 1972. {top['asset_id']} fails with {percent}% at the 90th percentile."
        )
        reply = ask(client, "How is SUB-07?")

    assert (reply["provider"], reply["fallback"]) == ("fake", False)


def test_an_invented_number_falls_back(make_client: ClientFactory) -> None:
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], "SUB-07 serves 12,000 customers.")
    with make_client(fake) as client:
        advance_to(client, 1)
        reply = ask(client, "How many customers does SUB-07 serve?")
        event = next(e for e in client.get("/audit").json() if e["type"] == "copilot_answered")

    assert (reply["provider"], reply["fallback"]) == ("template (fallback)", True)
    assert "12,000" in event["payload"]["fallback_reason"]


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
            "prompt_version": "copilot-v2",
            "latency_ms": 900,
            "usage": {"input_tokens": 500, "output_tokens": 80},
            "problems": [],
        }
    ]
    assert event["payload"]["tools_used"] == ["get_asset"]
    assert event["payload"]["citations"] == ["SUB-07"]
    assert event["versions"]["prompt_version"] == "copilot-v2", "the prompt the copilot loads"
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


def stream(client: TestClient, message: str) -> list[tuple[str, dict[str, Any]]]:
    """The server-sent events of one streamed turn, as (event, data) pairs."""
    response = client.post("/copilot/chat/stream", json={"message": message, "history": []})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_each_answer_says_how_it_got_there(make_client: ClientFactory) -> None:
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], "SUB-07 is a substation.")
    fake.model = "claude-sonnet-5-5"  # priced in config/llm.yaml
    with make_client(fake) as client:
        advance_to(client, 2)
        reply = ask(client, "Tell me about SUB-07")

    work = reply["work"]
    assert reply["advisory"] == 2
    assert [(c["name"], c["args"]) for c in work["tool_calls"]] == [
        ("get_asset", {"asset_id": "SUB-07"})
    ]
    assert work["tool_calls"][0]["result"]["id"] == "SUB-07"
    assert work["attempts"] == [
        {
            "provider": "fake",
            "model": "claude-sonnet-5-5",
            "prompt_version": "copilot-v2",
            "latency_ms": 900,
            "input_tokens": 500,
            "output_tokens": 80,
            "problems": [],
            "error": None,
        }
    ]
    assert (work["retries"], work["validated"], work["fallback"]) == (0, True, False)
    assert (work["provider"], work["model"], work["prompt_version"]) == (
        "fake",
        "claude-sonnet-5-5",
        "copilot-v2",
    )
    assert (work["input_tokens"], work["output_tokens"]) == (500, 80)
    assert work["cost_usd"] == pytest.approx((500 * 2.00 + 80 * 10.00) / 1_000_000)


def test_how_i_got_this_shows_no_restricted_field(make_client: ClientFactory) -> None:
    calls: list[tuple[str, dict[str, Any]]] = [
        ("get_asset", {"asset_id": "SUB-07"}),
        ("get_dependencies", {"asset_id": "SUB-07"}),
        ("explain_score", {"asset_id": "SUB-07", "advisory": None}),
    ]
    with make_client(FakeChat(calls, "SUB-07 is a substation.")) as client:
        advance_to(client, 2)
        reply = ask(client, "Tell me about SUB-07")

    shown = reply["work"]["tool_calls"]
    assert len(shown) == 3
    assert not keys(shown) & RESTRICTED_KEYS


def test_a_fallback_says_why_and_that_the_template_answered(make_client: ClientFactory) -> None:
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], "SUB-07 serves 12,000 customers.")
    with make_client(fake) as client:
        advance_to(client, 1)
        work = ask(client, "What depends on SUB-07?")["work"]

    assert (work["provider"], work["fallback"], work["validated"]) == (
        "template (fallback)",
        True,
        False,
    )
    assert work["attempts"][0]["problems"] == ["it states numbers no tool returned: 12,000"]
    assert "12,000" in work["fallback_reason"]
    assert [c["name"] for c in work["tool_calls"]] == ["get_dependencies"], "the template's"
    assert (work["model"], work["cost_usd"]) == (None, None), "fake-model has no price"


def test_the_stream_sends_each_step_then_the_validated_answer(make_client: ClientFactory) -> None:
    rejected = "SUB-07 serves 12,000 customers."
    fake = FakeChat([("get_asset", {"asset_id": "SUB-07"})], rejected)
    with make_client(fake) as client:
        advance_to(client, 1)
        events = stream(client, "What depends on SUB-07?")
        audited = [e for e in client.get("/audit").json() if e["type"] == "copilot_answered"]

    steps = [data for event, data in events if event == "step"]
    assert [event for event, _ in events] == ["step"] * len(steps) + ["answer"]
    assert [(s["kind"], s["tool"]) for s in steps] == [
        ("attempt", None),
        ("tool_call", "get_asset"),
        ("validating", None),
        ("rejected", None),
        ("fallback", None),
        ("tool_call", "get_dependencies"),
    ]
    assert steps[1]["args"] == {"asset_id": "SUB-07"}
    final = events[-1][1]
    assert "HOSP-01" in final["answer"] and final["work"]["fallback"] is True
    assert all(
        rejected not in json.dumps(s) and final["answer"] not in json.dumps(s) for s in steps
    )
    assert len(audited) == 1, "the streamed turn is audited once, like any other"


def test_the_stream_works_offline_with_the_template(client: TestClient) -> None:
    advance_to(client, 1)

    events = stream(client, "What depends on SUB-07?")

    assert [(e, d.get("kind")) for e, d in events] == [
        ("step", "attempt"),
        ("step", "tool_call"),
        ("step", "validating"),
        ("step", "validated"),
        ("answer", None),
    ]
    assert events[-1][1]["work"]["provider"] == "template"


def test_the_stream_validates_its_request(client: TestClient) -> None:
    response = client.post("/copilot/chat/stream", json={"message": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def failing_turn(error: Exception) -> Any:
    """Stands in for the copilot turn: one step, then the error."""

    def turn(*args: Any, on_step: Any, **kwargs: Any) -> Any:
        on_step(Step("attempt", 1, "template"))
        raise error

    return turn


def test_a_domain_error_in_the_stream_is_an_error_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes_copilot, "answer", failing_turn(DataNotLoaded("scenario missing")))

    events = stream(client, "What are the top risks?")

    assert [e for e, _ in events] == ["step", "error"]
    assert events[-1][1] == {"error": {"code": "data_not_loaded", "message": "scenario missing"}}


def test_an_unexpected_error_in_the_stream_is_a_generic_error_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes_copilot, "answer", failing_turn(RuntimeError("secret detail")))

    events = stream(client, "What are the top risks?")

    assert [e for e, _ in events] == ["step", "error"]
    assert events[-1][1] == {
        "error": {"code": "internal", "message": "the copilot could not answer"}
    }
    assert "secret detail" not in json.dumps(events)
