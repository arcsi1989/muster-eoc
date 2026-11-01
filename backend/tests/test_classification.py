"""Data classification (CR-03 C1): every contract field is public, internal or restricted, and
no restricted field reaches a model: not in a generation task's input, not in any copilot tool
result. Coordinates, elevation and the dependency graph are restricted (docs/decisions.md).

The leak checks go by key name, as the filter does: a restricted value under another key name,
or written into free text, would pass them. Each field name has one class in every contract
(checked at import), and no tool writes coordinates or graph edges into text."""

import json
from typing import Any, get_args

from muster.agent.lifecycle import draft_planning
from muster.classification import RESTRICTED_KEYS, contract_models, data_classes, for_model
from muster.copilot.chat import answer
from muster.copilot.tools import TOOL_DEFINITIONS
from muster.ids import ASSET_ID, mentioned
from muster.ingest.contracts import DataClass
from muster.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    ObjectivesRequest,
    ObjectivesResult,
    Prompt,
    ToolRunner,
)
from muster.llm.template import TemplateProvider
from muster.network import load_network
from tests.conftest import SeededFactory, SeededScenario


def keys(data: Any) -> set[str]:
    """Every key at any depth."""
    if isinstance(data, dict):
        return set(data) | {k for v in data.values() for k in keys(v)}
    if isinstance(data, list):
        return {k for v in data for k in keys(v)}
    return set()


def test_every_contract_field_has_a_data_class() -> None:
    models = contract_models()
    assert models
    for model in models:
        classes = data_classes(model)
        assert set(classes) == set(model.model_fields), model.__name__
        assert set(classes.values()) <= set(get_args(DataClass)), model.__name__


def test_coordinates_elevation_and_the_dependency_graph_are_restricted() -> None:
    assert {"x_km", "y_km", "elevation_m", "coordinates"} <= RESTRICTED_KEYS
    assert {"from_id", "to_id", "to_kind"} <= RESTRICTED_KEYS  # the edge list
    assert {
        "feeds",
        "fed_by",
        "downstream_assets",
    } <= RESTRICTED_KEYS  # what an asset feeds, is fed by
    assert not {"id", "name", "condition_score", "customers_served"} & RESTRICTED_KEYS


def test_the_filter_drops_restricted_fields_at_any_depth() -> None:
    data = {
        "id": "SUB-07",
        "x_km": 1.0,
        "sites": [{"id": "STG-02", "elevation_m": 3.0, "landfall": {"x_km": 2.0, "y_km": 3.0}}],
    }

    assert for_model(data) == {"id": "SUB-07", "sites": [{"id": "STG-02", "landfall": {}}]}


class Capturing:
    """A fake provider: calls every tool with every argument it is given and records what each
    returned to it, then answers with nothing it was not shown."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, calls: list[tuple[str, dict[str, Any]]]) -> None:
        self.calls = calls
        self.results: list[tuple[str, dict[str, Any]]] = []

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        raise NotImplementedError

    def rephrase_objectives(self, request: ObjectivesRequest, prompt: Prompt) -> ObjectivesResult:
        raise NotImplementedError

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult:
        self.results += [(name, run_tool(name, args)) for name, args in self.calls]
        return ChatResult("Done.", [n for n, _ in self.calls], self.model, prompt.version, 1, {})


def test_no_tool_result_contains_a_restricted_field(seeded: SeededScenario) -> None:
    seeded.issue_until(3)
    network = load_network(seeded.session)
    asset_calls: list[tuple[str, dict[str, Any]]] = []
    for asset_id in network.assets:
        asset_calls += [
            ("get_asset", {"asset_id": asset_id}),
            ("get_dependencies", {"asset_id": asset_id}),
            ("explain_score", {"asset_id": asset_id, "advisory": None}),
        ]
    other_calls: list[tuple[str, dict[str, Any]]] = [
        ("list_top_risks", {"advisory": None, "n": 10}),
        ("search_playbook", {"query": "generator hospital"}),
        ("search_playbook", {"query": "P-6.2"}),
        ("get_decision_package", {"advisory": None}),
        ("get_findings", {"advisory": None, "status": None}),
        ("get_outage_forecast", {"advisory": None}),
    ]
    provider = Capturing(asset_calls + other_calls)

    answer(seeded.session, seeded.playbook, provider, "Show me everything.", [], seeded.scoring)

    assert {name for name, _ in provider.results} == {d["name"] for d in TOOL_DEFINITIONS}
    for name, result in provider.results:
        assert "error" not in result, (name, result)
        assert not keys(result) & RESTRICTED_KEYS, name


def test_get_dependencies_shows_only_the_critical_facilities_an_asset_supports(
    seeded: SeededScenario,
) -> None:
    network = load_network(seeded.session)
    provider = Capturing([("get_dependencies", {"asset_id": a}) for a in network.assets])

    answer(seeded.session, seeded.playbook, provider, "Dependencies?", [], seeded.scoring)

    for (_, result), asset_id in zip(provider.results, network.assets, strict=True):
        others = mentioned(ASSET_ID, json.dumps(result)) - {asset_id}
        assert not others, (asset_id, others)  # no upstream feeders, no asset-to-asset edges
        assert set(result) == {"asset_id", "name", "critical_facilities", "serves_treatment_plant"}
        assert result["serves_treatment_plant"] == bool(network.treatment_plants_fed(asset_id))
        facilities = {f.id for f in network.direct_facilities(asset_id)}
        assert {f["id"] for f in result["critical_facilities"]} == facilities


def test_no_generation_input_contains_a_restricted_field(make_seeded: SeededFactory) -> None:
    """Every task a model is shown data for: the situation report and the IAP rephrasing, each
    through its own path (the advisory cycle, the planning draft)."""
    shown: dict[str, dict[str, Any]] = {}

    class Recording(TemplateProvider):
        def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
            shown["sitrep"] = request.shown()
            return super().draft_sitrep(request, prompt)

        def rephrase_objectives(
            self, request: ObjectivesRequest, prompt: Prompt
        ) -> ObjectivesResult:
            shown["objectives"] = request.shown()
            return super().rephrase_objectives(request, prompt)

    recording = Recording(top_risks=5, top_assets=3)
    with make_seeded(recording) as seeded:
        seeded.issue_until(3)
        draft_planning(seeded.session, seeded.playbook, seeded.cycle, seeded.scoring, recording, 3)

    assert set(shown) == {"sitrep", "objectives"}
    for task, data in shown.items():
        assert not keys(data) & RESTRICTED_KEYS, task


def test_the_finding_s_own_dependency_still_reaches_the_situation_report(
    make_seeded: SeededFactory,
) -> None:
    """The one dependency behind a finding is internal: P-6.2 and P-4.5 narrate it as before."""
    requests: list[DraftRequest] = []

    class Recording(TemplateProvider):
        def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
            requests.append(request)
            return super().draft_sitrep(request, prompt)

    with make_seeded(Recording(top_risks=5, top_assets=3)) as seeded:
        seeded.issue_until(3)

    request = requests[-1]
    actions = {(i["rule_id"], i["entity_id"]): i["action"] for i in request.shown()["items"]}
    assert "HOSP-01" in actions[("P-6.2", "SUB-07")]
    assert "WTP-01" in actions[("P-4.5", "PS-09")]
    assert [i["action"] for i in request.shown()["items"]] == [i.action for i in request.items]
