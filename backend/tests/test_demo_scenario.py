"""Seam 1: the advisory cycle through the API — the plan's section 8 scenario on both paths,
decisions by role, expiry on advance, reset, and the audit trail."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

PS14_OVERRIDE = "crew shortage, re-plan at next advisory"


def advance_to(client: TestClient, advisory: int) -> None:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200


def declare(client: TestClient, level: str, role: str, reason: str | None = None) -> Any:
    return client.post(
        "/activation/declare", json={"level": level, "declared_by": role, "reason": reason}
    )


def advance_declaring(client: TestClient, advisory: int) -> None:
    """The section 8 path: the Director declares `prepare` at advisory 1, the IC `full` at 3."""
    for number, level, role in ((1, "prepare", "director"), (3, "full", "incident_commander")):
        if number <= advisory:
            advance_to(client, number)
            declared = declare(client, level, role)
            assert declared.status_code == 200, declared.text
    advance_to(client, advisory)


def package(client: TestClient, advisory: int) -> dict[str, Any]:
    response = client.get(f"/packages/{advisory}")
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def item(pkg: dict[str, Any], rule_id: str, entity_id: str = "event") -> dict[str, Any]:
    return next(i for i in pkg["items"] if i["rule_id"] == rule_id and i["entity_id"] == entity_id)


def decide(
    client: TestClient,
    advisory: int,
    item_id: int,
    role: str,
    action: str,
    reason: str | None = None,
) -> Any:
    return client.post(
        f"/packages/{advisory}/items/{item_id}/decision",
        json={"role": role, "action": action, "reason": reason},
    )


def finding(
    client: TestClient, advisory: int, rule_id: str, entity_id: str = "event"
) -> dict[str, Any]:
    found = client.get("/findings", params={"advisory": advisory}).json()
    return next(f for f in found if f["rule_id"] == rule_id and f["entity_id"] == entity_id)


def scripted_decisions_at_advisory_3(client: TestClient, inspect_ps14: bool) -> None:
    advance_declaring(client, 3)
    pkg = package(client, 3)
    assert (pkg["activation_level"], pkg["decides_as_commander"]) == ("full", "incident_commander")
    assert (
        decide(client, 3, item(pkg, "P-4.5", "PS-09")["id"], "logistics", "approve").status_code
        == 200
    )
    hospital = decide(
        client, 3, item(pkg, "P-6.2", "SUB-07")["id"], "regulatory_liaison", "approve"
    )
    assert hospital.status_code == 200, hospital.text
    assert (
        decide(client, 3, item(pkg, "P-7.2")["id"], "regulatory_liaison", "approve").status_code
        == 200
    )
    ps14 = item(pkg, "P-4.2", "PS-14")["id"]
    if inspect_ps14:
        assert decide(client, 3, ps14, "operations", "approve").status_code == 200
    else:
        response = decide(client, 3, ps14, "incident_commander", "override", PS14_OVERRIDE)
        assert response.status_code == 200, response.text


def test_scripted_path_ps_14_override_leads_to_a_conflict_the_ic_decides(
    client: TestClient,
) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)

    advance_to(client, 4)
    assert finding(client, 4, "P-7.2")["status"] == "satisfied", "regulator notified at advisory 3"
    assert finding(client, 4, "P-4.6", "STG-02")["status"] == "open"
    advance_to(client, 5)
    pkg = package(client, 5)
    conflict = item(pkg, "P-4.2", "PS-14")
    assert conflict["kind"] == "conflict"
    assert conflict["cites"] == ["P-4.2", "P-4.7", "P-8.2"]
    assert finding(client, 5, "P-4.5", "PS-09")["status"] == "satisfied", "generator approved at 3"
    assert finding(client, 5, "P-6.2", "SUB-07")["status"] == "satisfied", "hospital confirmed at 3"
    recorded = next(
        e["payload"]["state_written"]
        for e in client.get("/audit", params={"actor": "human"}).json()
        if e["payload"].get("rule_id") == "P-6.2"
    )
    assert recorded == {
        "SUB-07.critical_customer_contacted": True,
        "SUB-07.hospital_backup_confirmed": True,
    }
    assert finding(client, 5, "P-7.2")["status"] == "satisfied"

    refused = decide(client, 5, conflict["id"], "operations", "defer", "too windy")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "decision_refused"
    decided = decide(
        client,
        5,
        conflict["id"],
        "incident_commander",
        "defer",
        "stop-work in force; inspect after landfall",
    )
    assert decided.status_code == 200
    after = item(decided.json(), "P-4.2", "PS-14")
    assert (after["status"], after["decided_by"]) == ("deferred", "incident_commander")


def test_alternative_path_ps_14_inspected_at_advisory_3_gives_no_conflict(
    client: TestClient,
) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=True)

    advance_to(client, 5)

    assert finding(client, 5, "P-4.2", "PS-14")["status"] == "satisfied"
    assert not any(
        i["rule_id"] == "P-4.2" and i["entity_id"] == "PS-14" for i in package(client, 5)["items"]
    )


def test_without_notifying_the_regulator_p_7_2_is_overdue_at_advisory_5(client: TestClient) -> None:
    advance_declaring(client, 5)

    regulator = item(package(client, 5), "P-7.2")

    assert regulator["overdue"] is True
    assert regulator["severity"] == "critical"


@pytest.mark.parametrize(
    ("role", "action", "reason", "why"),
    [
        ("planning", "approve", None, "P-4.5 belongs to logistics"),
        ("operations", "override", "busy", "only the Incident Commander overrides"),
        ("incident_commander", "override", None, "an override needs a reason"),
        ("director", "approve", None, "the IC is appointed at full activation"),
        ("logistics", "defer", "x", "defer applies to conflicts only"),
    ],
)
def test_refused_decisions_change_nothing(
    client: TestClient, role: str, action: str, reason: str | None, why: str
) -> None:
    advance_declaring(client, 3)
    target = item(package(client, 3), "P-4.5", "PS-09")

    response = decide(client, 3, target["id"], role, action, reason)

    assert response.status_code == 403, why
    assert item(package(client, 3), "P-4.5", "PS-09")["status"] == "pending"


def test_below_full_activation_the_director_holds_the_command_role(client: TestClient) -> None:
    advance_to(client, 1)
    pkg = package(client, 1)
    assert pkg["decides_as_commander"] == "director"

    as_ic = decide(client, 1, item(pkg, "P-4.1")["id"], "incident_commander", "approve")
    as_director = decide(client, 1, item(pkg, "P-4.1")["id"], "director", "approve")

    assert as_ic.status_code == 403
    assert "Director" in as_ic.json()["error"]["message"]
    assert as_director.status_code == 200


def test_a_decided_item_cannot_be_decided_again(client: TestClient) -> None:
    advance_to(client, 1)
    target = item(package(client, 1), "P-4.1")["id"]
    decide(client, 1, target, "planning", "approve")

    again = decide(client, 1, target, "director", "override", "changed my mind")

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_decided"


def test_approval_writes_the_state_that_satisfies_the_rule(client: TestClient) -> None:
    advance_to(client, 1)
    gap = finding(client, 1, "P-4.3")
    needed = gap["details"]["event.wtp_pump_stations_top25"]
    decide(client, 1, item(package(client, 1), "P-4.3")["id"], "logistics", "approve")
    decide(client, 1, item(package(client, 1), "P-4.1")["id"], "planning", "approve")

    advance_to(client, 2)

    fuel = finding(client, 2, "P-4.3")
    assert fuel["details"]["event.generators_fuelled"] == needed
    assert fuel["status"] == (
        "satisfied" if fuel["details"]["event.wtp_pump_stations_top25"] <= needed else "open"
    )
    assert finding(client, 2, "P-4.1")["status"] == "open", (
        "the review holds for one operational period"
    )


def test_undecided_items_close_as_not_decided_when_the_next_advisory_arrives(
    client: TestClient,
) -> None:
    advance_to(client, 1)
    assert package(client, 1)["status"] == "open"

    advance_to(client, 2)

    closed = package(client, 1)
    assert closed["status"] == "closed"
    assert {i["status"] for i in closed["items"]} == {"not_decided"}
    late = decide(client, 1, closed["items"][0]["id"], "director", "approve")
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "package_closed"
    assert any(e["type"] == "items_not_decided" for e in client.get("/audit").json())


def test_sitrep_rule_is_never_a_package_item(client: TestClient) -> None:
    advance_to(client, 1)

    assert not any(i["rule_id"] == "P-7.1" for i in package(client, 1)["items"])
    assert finding(client, 1, "P-7.1")["status"] == "open"


def test_the_generator_action_is_offered_on_pumping_stations_only(client: TestClient) -> None:
    types = {a["id"]: a["type"] for a in client.get("/assets").json()}
    for advisory in (3, 4, 5):
        advance_to(client, advisory)
        generators = [i for i in package(client, advisory)["items"] if i["rule_id"] == "P-4.5"]

        assert generators, f"P-4.5 items at advisory {advisory}"
        assert {types[i["entity_id"]] for i in generators} == {"pump_station"}


def test_reset_restores_the_initial_state(client: TestClient) -> None:
    scripted_decisions_at_advisory_3(client, inspect_ps14=True)

    assert client.post("/advisories/reset").status_code == 200
    advance_to(client, 3)

    assert finding(client, 3, "P-4.5", "PS-09")["status"] == "open"
    assert finding(client, 3, "P-4.2", "PS-14")["status"] == "open"
    assert item(package(client, 3), "P-4.5", "PS-09")["status"] == "pending"
    assert package(client, 3)["activation_level"] == "monitor", "the declarations are undone"


def test_every_node_and_decision_is_audited(client: TestClient) -> None:
    advance_to(client, 1)
    decide(client, 1, item(package(client, 1), "P-4.1")["id"], "planning", "approve")

    events = client.get("/audit").json()
    types = {e["type"] for e in events}
    human = client.get("/audit", params={"actor": "human"}).json()

    assert {"context_loaded", "diff", "rules_evaluated", "sitrep_drafted", "decision"} <= types
    graph_steps = [
        e
        for e in events
        if e["type"] in {"context_loaded", "diff", "rules_evaluated", "sitrep_drafted", "decision"}
    ]
    assert all(e["versions"]["rules_version"] == "3.3" for e in graph_steps)
    assert all(e["advisory_no"] == 1 and e["hours_to_landfall"] == 72 for e in events)
    assert [e["type"] for e in human] == ["decision"]
    assert human[0]["payload"]["state_written"] == {"event.risk_list_reviewed_current": True}
    assert human[0]["input_hash"]


def test_package_errors(client: TestClient) -> None:
    assert client.get("/packages/1").status_code == 404
    advance_to(client, 1)

    assert decide(client, 1, 99999, "planning", "approve").status_code == 404
    bad_role = client.post(
        "/packages/1/items/1/decision", json={"role": "mayor", "action": "approve"}
    )
    assert bad_role.status_code == 422


def test_advisory_2_logs_top_10_changes_in_the_diff(client: TestClient) -> None:
    advance_to(client, 2)

    diff = next(
        e for e in client.get("/audit").json() if e["type"] == "diff" and e["advisory_no"] == 2
    )
    changes = package(client, 2)["changes"]

    assert diff["payload"]["rank_moves"] == changes["rank_moves"]
    assert changes["previous_advisory_no"] == 1
    assert changes["rank_moves"], "the forecast changes, so the ranking moves"


def test_advisory_4_has_barrier_items_and_regulator_not_yet_overdue(client: TestClient) -> None:
    advance_declaring(client, 4)
    pkg = package(client, 4)

    assert any(i["rule_id"] == "P-5.1" for i in pkg["items"])
    assert item(pkg, "P-4.6", "STG-02")["kind"] == "gap"
    assert item(pkg, "P-7.2")["overdue"] is False


@pytest.mark.parametrize(
    ("action", "reason", "why"),
    [
        ("defer", None, "a conflict decision needs a reason"),
        ("approve", None, "a conflict is never approved"),
        ("override", "x", "a conflict is never overridden"),
    ],
)
def test_conflict_refusals(client: TestClient, action: str, reason: str | None, why: str) -> None:
    advance_declaring(client, 5)
    conflict = item(package(client, 5), "P-4.2", "PS-14")

    response = decide(client, 5, conflict["id"], "incident_commander", action, reason)

    assert response.status_code == 403, why


def test_an_alternative_measure_is_recorded_without_changing_state(client: TestClient) -> None:
    advance_declaring(client, 5)
    conflict = item(package(client, 5), "P-4.2", "PS-14")

    decided = decide(
        client, 5, conflict["id"], "incident_commander", "alternative", "remote monitoring only"
    )

    assert item(decided.json(), "P-4.2", "PS-14")["status"] == "alternative"
    human = client.get("/audit", params={"actor": "human"}).json()
    assert human[0]["type"] == "decision"
    assert human[0]["payload"]["state_written"] == {}


def test_below_full_activation_the_director_decides_a_conflict(client: TestClient) -> None:
    advance_to(client, 5)  # Full never declared
    conflict = item(package(client, 5), "P-4.2", "PS-14")

    as_ic = decide(client, 5, conflict["id"], "incident_commander", "defer", "stop-work")
    as_director = decide(client, 5, conflict["id"], "director", "defer", "stop-work")

    assert as_ic.status_code == 403
    assert as_director.status_code == 200, as_director.text
