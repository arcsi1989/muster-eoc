"""Agent tracing (CR-03 C3): every advisory-cycle node and every grounded generation is a span in
the trace_span table, read back per advisory with totals for the advisory and the demo run.
Template mode costs nothing; a fake provider forces the retry and the fallback (T2)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.llm.config import load_llm_config
from app.llm.schemas import LLMUnavailable, Paragraph
from tests.conftest import ClientFactory, FakeProvider, draft_of

CYCLE_NODES = {
    "load_context",
    "diff",
    "evaluate_rules",
    "draft",
    "await_approval",
    "apply_decision",
    "finalise",
}
INVENTED = draft_of(Paragraph(text="SUB-99 floods (P-9.9).", clause_ids=["P-9.9"], asset_ids=[]))
PRICED_MODEL = "claude-sonnet-5-5"  # $2 in, $10 out per million tokens (config/llm.yaml)


def _trace(client: TestClient, advisory_no: int) -> dict[str, Any]:
    response = client.get(f"/advisories/{advisory_no}/trace")
    assert response.status_code == 200
    trace: dict[str, Any] = response.json()
    return trace


def _spans(trace: dict[str, Any], node: str) -> list[dict[str, Any]]:
    return [s for s in trace["spans"] if s["node"] == node]


@pytest.mark.parametrize("advisory_no", [1, 2])
def test_every_advisory_cycle_produces_a_complete_trace(
    client: TestClient, advisory_no: int
) -> None:
    for _ in range(advisory_no + 1):  # the next advisory expires it: its cycle runs to finalise
        assert client.post("/advisories/next").is_success

    trace = _trace(client, advisory_no)

    nodes = {s["node"] for s in trace["spans"] if s["kind"] == "cycle_node"}
    assert nodes == CYCLE_NODES
    assert all(s["advisory_no"] == advisory_no for s in trace["spans"])
    assert "paused" in {s["status"] for s in _spans(trace, "await_approval")}
    assert {s["status"] for s in trace["spans"] if s["node"] != "await_approval"} == {"ok"}
    [draft_node] = _spans(trace, "draft")
    [generation] = _spans(trace, "sitrep_draft")
    assert generation["kind"] == "generation"
    assert generation["parent_span_id"] == draft_node["span_id"]
    assert generation["validation"] == "passed"
    assert trace["advisory_totals"]["latency_ms"] > 0


def test_template_mode_shows_zero_tokens_and_zero_cost(client: TestClient) -> None:
    client.post("/advisories/next")
    assert client.post("/copilot/chat", json={"message": "What are the top risks?"}).is_success

    trace = _trace(client, 1)

    [turn] = _spans(trace, "copilot")
    assert turn["kind"] == "generation"
    assert turn["parent_span_id"] not in {s["span_id"] for s in trace["spans"]}  # not in a node
    assert turn["provider"] == "template"
    for span in trace["spans"]:
        assert (span["tokens_in"], span["tokens_out"], span["cost_usd"]) == (0, 0, 0.0)
    for totals in (trace["advisory_totals"], trace["run_totals"]):
        assert (totals["tokens_in"], totals["tokens_out"], totals["cost_usd"]) == (0, 0, 0.0)
        assert totals["unpriced_spans"] == 0


def test_a_rejected_draft_shows_the_retry_and_the_template_fallback(
    make_client: ClientFactory,
) -> None:
    provider = FakeProvider(INVENTED)  # every draft cites what the request does not show
    provider.model = PRICED_MODEL
    with make_client(provider) as client:
        client.post("/advisories/next")
        trace = _trace(client, 1)

    [generation] = _spans(trace, "sitrep_draft")
    assert generation["retries"] == 1  # draft.retries in scoring.yaml
    assert len(generation["attempts"]) == 2
    assert generation["fallback"] is True
    assert generation["provider"] == "template (fallback)"
    assert generation["validation"] == "failed"
    assert generation["fallback_reason"].startswith("citations failed validation")
    # both rejected attempts were paid for: 2 x (100 in, 50 out)
    assert (generation["tokens_in"], generation["tokens_out"]) == (200, 100)
    assert generation["cost_usd"] == pytest.approx(2 * (100 * 2 + 50 * 10) / 1e6)
    assert trace["advisory_totals"]["tokens_in"] == 200
    assert trace["advisory_totals"]["retries"] == 1
    assert trace["advisory_totals"]["fallbacks"] == 1
    assert trace["advisory_totals"]["cost_usd"] == pytest.approx(generation["cost_usd"])


def test_an_unavailable_provider_shows_the_error_and_the_template_fallback(
    make_client: ClientFactory,
) -> None:
    with make_client(FakeProvider(LLMUnavailable("the model call timed out"))) as client:
        client.post("/advisories/next")
        trace = _trace(client, 1)

    [generation] = _spans(trace, "sitrep_draft")
    assert generation["validation"] == "error"
    assert generation["retries"] == 0  # a provider failure is not retried
    assert generation["fallback"] is True
    assert generation["fallback_reason"] == "the model call timed out"
    assert generation["cost_usd"] == 0.0


def test_tokens_from_a_model_without_a_price_have_no_cost_estimate(
    make_client: ClientFactory,
) -> None:
    with make_client(FakeProvider(INVENTED)) as client:  # fake-model is not in llm.yaml
        client.post("/advisories/next")
        trace = _trace(client, 1)

    [generation] = _spans(trace, "sitrep_draft")
    assert generation["tokens_in"] == 200
    assert generation["cost_usd"] is None
    assert trace["advisory_totals"]["unpriced_spans"] == 1


def test_the_run_totals_cover_every_advisory_of_the_run(client: TestClient) -> None:
    client.post("/advisories/next")
    client.post("/advisories/next")

    first, second = _trace(client, 1), _trace(client, 2)

    assert first["run_id"] == second["run_id"]
    assert first["run_totals"] == second["run_totals"]
    assert first["run_totals"]["latency_ms"] == pytest.approx(
        first["advisory_totals"]["latency_ms"] + second["advisory_totals"]["latency_ms"]
    )


def test_a_scenario_reset_clears_the_traces_and_begins_a_new_run(client: TestClient) -> None:
    client.post("/advisories/next")
    before = _trace(client, 1)

    client.post("/advisories/reset")
    client.post("/advisories/next")
    after = _trace(client, 1)

    assert after["run_id"] != before["run_id"]
    assert len(_spans(after, "sitrep_draft")) == 1  # the earlier run's spans are gone


def test_the_trace_of_an_advisory_not_yet_issued_is_not_found(client: TestClient) -> None:
    response = client.get("/advisories/1/trace")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_prices_estimate_cost_per_million_tokens() -> None:
    config = load_llm_config(REPO_ROOT / "config" / "llm.yaml")

    assert config.cost_usd(PRICED_MODEL, 1_000_000, 1_000_000) == pytest.approx(12.0)
    assert config.cost_usd(None, 0, 0) == 0.0  # the template
    assert config.cost_usd("unknown-model", 10, 10) is None
