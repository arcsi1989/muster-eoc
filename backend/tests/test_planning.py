"""CR-02 C3: the ICS-215 and IAP objectives drafted for the next operational period, and their
release by the Planning Section Chief and then the commanding role."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.llm.grounded import FALLBACK_LABEL
from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    IapObjective,
    LLMUnavailable,
    ObjectivesRequest,
    ObjectivesResult,
    ObjectiveWording,
    Prompt,
    ToolRunner,
)
from app.llm.template import TemplateProvider
from app.models import Finding
from app.planning.objectives import objectives, reword
from tests.conftest import ClientFactory, SeededScenario
from tests.test_demo_scenario import (
    advance_to,
    decide,
    package,
    scripted_decisions_at_advisory_3,
)


def draft(client: TestClient, advisory: int) -> Any:
    return client.post(f"/packages/{advisory}/planning/draft")


def release(client: TestClient, advisory: int, role: str) -> Any:
    return client.post(f"/packages/{advisory}/planning/release", json={"role": role})


def approve_flood_barriers(client: TestClient, advisory: int) -> list[str]:
    """Logistics approves every P-5.1 flood barrier item; returns their substations."""
    barriers = [i for i in package(client, advisory)["items"] if i["rule_id"] == "P-5.1"]
    for barrier in barriers:
        assert decide(client, advisory, barrier["id"], "logistics", "approve").status_code == 200
    return [b["entity_id"] for b in barriers]


def approved_item_ids(client: TestClient, *advisories: int) -> set[int]:
    return {
        i["id"]
        for advisory in advisories
        for i in package(client, advisory)["items"]
        if i["status"] == "approved"
    }


def test_after_advisory_3_decisions_the_ics_215_lists_the_generator_and_flood_barriers(
    client: TestClient,
) -> None:
    """The PS-09 generator is approved at advisory 3; flood barriers (P-5.1, from T-36) are
    approved at advisory 4, where the ICS-215 for the next period is drafted (CR-02 demo)."""
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)
    advance_to(client, 4)
    substations = approve_flood_barriers(client, 4)
    assert len(substations) == 5

    drafted = draft(client, 4)

    assert drafted.status_code == 200, drafted.text
    worksheet = drafted.json()
    assert worksheet["status"] == "DRAFT"
    assert (worksheet["period_start_hours"], worksheet["period_end_hours"]) == (24, 12)
    rows = {(r["clause_id"], r["location_id"]): r for r in worksheet["ics215"]}
    assert set(rows) == {("P-4.5", "PS-09")} | {("P-5.1", s) for s in substations}
    generator = rows["P-4.5", "PS-09"]
    assert generator["resource_kind"] == "Portable generator"
    # six generators are fuelled; PS-09 is the only one assigned
    assert (generator["required"], generator["have"], generator["need"]) == (1, 1, 0)
    barrier_rows = [r for r in worksheet["ics215"] if r["clause_id"] == "P-5.1"]
    assert {r["resource_kind"] for r in barrier_rows} == {"Flood barrier crew"}
    # one barrier crew per usable staging area: four, since STG-02 floods from advisory 4
    assert [(r["required"], r["have"], r["need"]) for r in barrier_rows] == [(1, 1, 0)] * 4 + [
        (1, 0, 1)
    ]
    assert all(r["reporting_location_id"] not in (None, "STG-02") for r in worksheet["ics215"])
    assert {r["requested_arrival_hours"] for r in worksheet["ics215"]} == {24}


def test_nothing_unapproved_appears_in_the_ics_215(client: TestClient) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)  # PS-14 inspection overridden
    advance_to(client, 4)
    approve_flood_barriers(client, 4)

    rows = draft(client, 4).json()["ics215"]

    assert {r["item_id"] for r in rows} <= approved_item_ids(client, 3, 4)
    assert ("P-4.2", "PS-14") not in {(r["clause_id"], r["location_id"]) for r in rows}
    # P-4.5 opened for ten pumping stations; only PS-09's generator was approved
    assert [r["location_id"] for r in rows if r["clause_id"] == "P-4.5"] == ["PS-09"]


def test_a_task_under_stop_work_is_marked_on_its_row(client: TestClient) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)
    advance_to(client, 5)

    rows = draft(client, 5).json()["ics215"]

    generator = next(r for r in rows if r["location_id"] == "PS-09")
    assert generator["stop_work"] == ["P-4.7"]
    assert generator["requested_arrival_hours"] == 12


def test_iap_objectives_number_three_to_six_and_cite_every_open_finding(
    seeded: SeededScenario,
) -> None:
    for advisory in range(1, 6):
        seeded.issue_until(advisory)
        stored = seeded.session.exec(select(Finding).where(Finding.advisory_no == advisory)).all()

        drafted = objectives(stored, by_hours=36)

        assert 3 <= len(drafted) <= 6, advisory
        cited = {c for o in drafted for c in o.clause_ids}
        assert {f.rule_id for f in stored if f.status != "satisfied"} <= cited, advisory
        assert all(o.clause_ids and o.text.endswith("by T-36") for o in drafted[1:]), advisory


def test_conflicts_bring_a_safety_objective_first(seeded: SeededScenario) -> None:
    seeded.issue_until(5)
    stored = seeded.session.exec(select(Finding).where(Finding.advisory_no == 5)).all()

    safety = objectives(stored, by_hours=12)[0]

    assert safety.text.startswith("Keep crews safe")
    assert {"P-4.7", "P-8.2", "P-4.2"} <= set(safety.clause_ids)
    assert "PS-14" in safety.entity_ids


def test_every_playbook_rule_that_can_be_open_has_an_objective(seeded: SeededScenario) -> None:
    rules = [r for r in seeded.playbook.rulebook.rules if r.kind != "prohibition"]
    findings = [
        Finding(
            advisory_no=1,
            rule_id=r.id,
            entity_id="event",
            entity_kind="event",
            status="open",
            severity=r.severity,
            owner_role=r.owner_role,
            cites=[r.id],
            overdue=False,
            details={},
        )
        for r in rules
    ]

    drafted = objectives(findings, by_hours=24)

    assert {r.id for r in rules} <= {c for o in drafted for c in o.clause_ids}


def test_with_nothing_open_the_standing_objectives_still_make_three() -> None:
    """Safety stands first; the risk list review and the situation report are due again every
    operational period (P-4.1, P-7.1), split into two objectives to reach the floor of three."""
    drafted = objectives([], by_hours=48)

    assert [o.clause_ids for o in drafted] == [["P-4.7", "P-8.2"], ["P-4.1"], ["P-7.1"]]
    assert drafted[0].text == "Keep crews safe: no field work where stop-work applies"
    assert drafted[2].text == (
        "Keep the EOC in step with the storm: approve the situation report by T-48"
    )


def test_safety_leads_even_without_conflicts(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    stored = seeded.session.exec(select(Finding).where(Finding.advisory_no == 1)).all()

    safety = objectives(stored, by_hours=60)[0]

    assert (safety.clause_ids, safety.entity_ids) == (["P-4.7", "P-8.2"], [])


OBJECTIVES = ObjectivesRequest(
    3,
    [
        IapObjective(
            text="Protect the water supply to the treatment plant: assign generators by T-36",
            clause_ids=["P-4.5"],
            entity_ids=["PS-09"],
        ),
        IapObjective(
            text="Keep the EOC in step with the storm: notify the regulator by T-36",
            clause_ids=["P-7.2"],
            entity_ids=[],
        ),
    ],
)
TEMPLATE = TemplateProvider(top_risks=5, top_assets=5)
PROMPT = Prompt("fake-iap-v1", "system", 100)


class FakeRephraser:
    """A fake provider: returns the given wordings in turn (or raises them) and records the
    feedback each try was sent."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, *outputs: list[str] | Exception) -> None:
        self.outputs = list(outputs)
        self.feedback: list[list[str]] = []

    def rephrase_objectives(self, request: ObjectivesRequest, prompt: Prompt) -> ObjectivesResult:
        self.feedback.append(request.feedback)
        output = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(output, Exception):
            raise output
        return ObjectivesResult(
            ObjectiveWording(texts=output), self.name, self.model, prompt.version, 9, {}
        )

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
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


GROUNDED = ["Keep WTP water flowing: generator at PS-09 by T-36 (P-4.5)", "Notify the regulator"]


def test_a_grounded_rewording_is_used() -> None:
    outcome = reword(FakeRephraser(GROUNDED), TEMPLATE, PROMPT, OBJECTIVES, attempts=2)

    assert outcome.result.wording.texts == GROUNDED
    assert (outcome.provider, outcome.fallback, outcome.prompt_version) == (
        "fake",
        False,
        "fake-iap-v1",
    )


@pytest.mark.parametrize(
    ("wording", "problem"),
    [
        (["Generators at PS-09 (P-4.3)", "Notify"], "objective 1 mentions clause P-4.3"),
        (["Generators at PS-14", "Notify"], "objective 1 mentions PS-14"),
        (["Generators and the regulator"], "expected 2 objectives, got 1"),
        (["Generators", " "], "objective 2 is empty"),
    ],
)
def test_an_ungrounded_rewording_is_retried_then_the_template_wording_stands(
    wording: list[str], problem: str
) -> None:
    fake = FakeRephraser(wording)

    outcome = reword(fake, TEMPLATE, PROMPT, OBJECTIVES, attempts=2)

    assert any(problem in p for p in fake.feedback[1]), "the retry is told what was wrong"
    assert (outcome.provider, outcome.fallback) == (FALLBACK_LABEL, True)
    assert outcome.result.wording.texts == [o.text for o in OBJECTIVES.objectives]
    assert outcome.fallback_reason is not None
    assert outcome.fallback_reason.startswith("objective citations failed validation")


def test_a_failing_provider_falls_back_to_the_template_wording() -> None:
    outcome = reword(
        FakeRephraser(LLMUnavailable("down")), TEMPLATE, PROMPT, OBJECTIVES, attempts=2
    )

    assert (outcome.provider, outcome.fallback_reason) == (FALLBACK_LABEL, "down")
    assert outcome.result.wording.texts == [o.text for o in OBJECTIVES.objectives]


def test_the_draft_keeps_the_citations_when_a_model_rewords_the_objectives(
    make_client: ClientFactory,
) -> None:
    with make_client(FakeRephraser(LLMUnavailable("unused"))) as client:
        advance_to(client, 1)
        template = draft(client, 1).json()["objectives"]
    fake = FakeRephraser([f"Objective {n}" for n in range(len(template))])
    with make_client(fake) as client:
        advance_to(client, 1)

        drafted = draft(client, 1).json()

    assert [o["text"] for o in drafted["objectives"]] == [
        f"Objective {n}" for n in range(len(template))
    ]
    assert [o["clause_ids"] for o in drafted["objectives"]] == [o["clause_ids"] for o in template]
    assert (drafted["provider"], drafted["fallback"]) == ("fake", False)


def test_the_template_provider_keeps_the_wording_and_is_no_fallback(client: TestClient) -> None:
    advance_to(client, 1)

    drafted = draft(client, 1).json()

    assert (drafted["provider"], drafted["fallback"], drafted["prompt_version"]) == (
        "template",
        False,
        None,
    )
    assert drafted["objectives"][1]["text"].endswith("by T-60")


def test_release_takes_the_planning_section_chief_then_the_incident_commander(
    client: TestClient,
) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)  # Full declared at advisory 3
    assert release(client, 3, "planning").status_code == 404, "nothing drafted yet"
    assert draft(client, 3).status_code == 200

    commander_first = release(client, 3, "incident_commander")
    assert commander_first.status_code == 403
    assert commander_first.json()["error"]["code"] == "decision_refused"
    approved = release(client, 3, "planning")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "DRAFT", "one approval does not release"
    assert approved.json()["planning_approved_at"] is not None
    assert release(client, 3, "planning").status_code == 403, "the second approval is not Planning"
    assert release(client, 3, "logistics").status_code == 403
    assert draft(client, 3).json()["error"]["code"] == "planning_in_release"

    released = release(client, 3, "incident_commander")

    assert released.status_code == 200, released.text
    body = released.json()
    assert (body["status"], body["released_by"]) == ("released", "incident_commander")
    again = release(client, 3, "incident_commander")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "planning_released")
    assert client.get("/packages/3/planning").json()["status"] == "released"
    logged = [
        (e["type"], e["payload"]["role"], e["summary"])
        for e in client.get("/audit", params={"actor": "human"}).json()
        if e["type"].startswith("planning_")
    ]
    assert sorted(logged) == [
        ("planning_approved", "planning", "Planning Section Chief approved the planning draft"),
        (
            "planning_released",
            "incident_commander",
            "Incident commander released the ICS-215 and IAP objectives",
        ),
    ]


def test_below_full_activation_the_director_releases(client: TestClient) -> None:
    advance_to(client, 1)
    draft(client, 1)
    assert release(client, 1, "planning").status_code == 200

    assert release(client, 1, "incident_commander").status_code == 403
    assert release(client, 1, "director").json()["status"] == "released"


def test_a_closed_package_is_neither_drafted_nor_released(client: TestClient) -> None:
    advance_to(client, 1)
    draft(client, 1)
    advance_to(client, 2)

    for refused in (draft(client, 1), release(client, 1, "planning")):
        assert (refused.status_code, refused.json()["error"]["code"]) == (409, "package_closed")
    assert client.get("/packages/1/planning").json()["status"] == "DRAFT"


def test_a_scenario_reset_deletes_the_planning_drafts(client: TestClient) -> None:
    advance_to(client, 1)
    draft(client, 1)

    assert client.post("/advisories/reset").status_code == 200

    assert client.get("/packages/1/planning").status_code == 404
