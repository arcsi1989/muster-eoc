"""Seam 1: activation is declared, not computed (P-2.5, CR-01 C3). The P-2.5 proposal, the
declaration through the API, who may declare, and the P-7.2 clock from the declaration."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

ROLES_BY_OWNER = {"incident_commander": "director"}  # the IC's items go to the Director below Full


def advance_to(client: TestClient, advisory: int) -> None:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200


def package(client: TestClient, advisory: int) -> dict[str, Any]:
    response = client.get(f"/packages/{advisory}")
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def proposal(client: TestClient, advisory: int) -> dict[str, Any] | None:
    return next((i for i in package(client, advisory)["items"] if i["rule_id"] == "P-2.5"), None)


def declare(client: TestClient, level: str, role: str, reason: str | None = None) -> Any:
    return client.post(
        "/activation/declare", json={"level": level, "declared_by": role, "reason": reason}
    )


def findings(client: TestClient, advisory: int, rule_id: str) -> list[dict[str, Any]]:
    found = client.get("/findings", params={"advisory": advisory}).json()
    return [f for f in found if f["rule_id"] == rule_id]


def test_advisory_1_proposes_level_2_at_the_top_of_the_package(client: TestClient) -> None:
    advance_to(client, 1)
    pkg = package(client, 1)

    first = pkg["items"][0]
    assert (pkg["activation_level"], pkg["proposed_activation_level"]) == ("monitor", "prepare")
    assert (first["rule_id"], first["kind"], first["status"]) == ("P-2.5", "proposal", "pending")
    assert first["owner_role"] == "director", "the Director declares Level 2"
    assert first["proposed_action"].startswith("Declare activation Level 2 (prepare)")


def test_declaring_closes_the_proposal_and_is_recorded(client: TestClient) -> None:
    advance_to(client, 1)

    response = declare(client, "prepare", "director", "storm on track, T-72")

    assert response.status_code == 200, response.text
    body = response.json()
    closed = next(i for i in body["items"] if i["rule_id"] == "P-2.5")
    assert (closed["status"], closed["decided_by"], closed["reason"]) == (
        "approved",
        "director",
        "storm on track, T-72",
    )
    assert closed["decided_at"]
    assert (body["activation_level"], body["decides_as_commander"]) == ("prepare", "director")
    event = next(e for e in client.get("/audit", params={"actor": "human"}).json())
    assert event["type"] == "activation_declared"
    assert (
        event["summary"] == "Director declared activation Level 2 (prepare): storm on track, T-72"
    )
    assert event["payload"]["from_level"] == "monitor"
    assert event["payload"]["state_written"] == {
        "event.activation_level": "prepare",
        "event.activation_declared_at_hours": 72,
    }

    advance_to(client, 2)
    assert proposal(client, 2) is None, "the declared level is the proposed one at T-60"
    again = declare(client, "prepare", "director")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "no_activation_proposal"


@pytest.mark.parametrize(
    ("advisory", "level", "role", "why"),
    [
        (1, "prepare", "incident_commander", "the Director declares Level 2"),
        (1, "prepare", "planning", "planning never declares"),
        (3, "full", "director", "the Incident Commander declares Level 1"),
        (1, "full", "incident_commander", "only the proposed level can be declared"),
    ],
)
def test_a_wrong_declaration_is_refused_and_changes_nothing(
    client: TestClient, advisory: int, level: str, role: str, why: str
) -> None:
    advance_to(client, advisory)

    response = declare(client, level, role)

    assert response.status_code == 403, why
    assert response.json()["error"]["code"] == "decision_refused"
    pkg = package(client, advisory)
    assert pkg["activation_level"] == "monitor"
    assert proposal(client, advisory)["status"] == "pending"  # type: ignore[index]
    assert client.get("/audit", params={"actor": "human"}).json() == []


def test_a_declaration_needs_an_open_package(client: TestClient) -> None:
    response = declare(client, "prepare", "director")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "package_closed"


def test_an_unknown_level_is_a_validation_error(client: TestClient) -> None:
    advance_to(client, 1)

    assert declare(client, "level_0", "director").status_code == 422


def test_p_2_5_is_never_closed_without_a_declaration(client: TestClient) -> None:
    advance_to(client, 1)
    item_id = proposal(client, 1)["id"]  # type: ignore[index]

    for role, action, reason in (
        ("director", "approve", None),
        ("incident_commander", "approve", None),
        ("director", "override", "not needed yet"),
    ):
        response = client.post(
            f"/packages/1/items/{item_id}/decision",
            json={"role": role, "action": action, "reason": reason},
        )
        assert response.status_code == 403, (role, action)
    assert proposal(client, 1)["status"] == "pending"  # type: ignore[index]

    advance_to(client, 2)

    assert proposal(client, 1)["status"] == "not_decided"  # type: ignore[index]
    assert findings(client, 2, "P-2.5")[0]["status"] == "open", "proposed again"


def test_p_7_2_is_inactive_before_full_is_declared_and_overdue_12_hours_after(
    client: TestClient,
) -> None:
    advance_to(client, 3)
    assert findings(client, 3, "P-7.2") == [], "Full is proposed, not declared"
    assert package(client, 3)["decides_as_commander"] == "director"

    declared = declare(client, "full", "incident_commander").json()

    regulator = next(i for i in declared["items"] if i["rule_id"] == "P-7.2")
    assert regulator["status"] == "pending", "the declaration adds the notification item"
    assert declared["decides_as_commander"] == "incident_commander"
    (at_3,) = findings(client, 3, "P-7.2")
    assert (at_3["overdue"], at_3["details"]["event.hours_since_full_activation"]) == (False, 0)
    advance_to(client, 4)
    (at_4,) = findings(client, 4, "P-7.2")
    assert (at_4["overdue"], at_4["details"]["event.hours_since_full_activation"]) == (False, 12)
    advance_to(client, 5)
    (at_5,) = findings(client, 5, "P-7.2")
    assert (at_5["overdue"], at_5["severity"]) == (True, "critical")


def test_rules_gated_by_hours_still_use_hours_to_landfall(client: TestClient) -> None:
    advance_to(client, 3)

    assert findings(client, 3, "P-4.5"), "P-4.5 is active from 48 h, whatever the level"
    assert package(client, 3)["activation_level"] == "monitor"


def test_the_timeline_shows_the_level_in_force_at_each_advisory(client: TestClient) -> None:
    advance_to(client, 1)
    declare(client, "prepare", "director")
    advance_to(client, 3)
    declare(client, "full", "incident_commander")

    timeline = client.get("/advisories").json()["timeline"]

    assert [s["activation_level"] for s in timeline] == ["prepare", "prepare", "full", None, None]
    changes = client.get("/advisories/3/changes").json()
    assert (changes["activation_level_from"], changes["activation_level_to"]) == ("prepare", "full")


def test_no_code_path_but_a_declaration_sets_the_activation_level(client: TestClient) -> None:
    """Every other decision a person can take, at every advisory: the level stays declared."""
    for advisory in range(1, 6):
        advance_to(client, advisory)
        pkg = package(client, advisory)
        for pending in (i for i in pkg["items"] if i["kind"] == "gap"):
            role = ROLES_BY_OWNER.get(pending["owner_role"], pending["owner_role"])
            client.post(
                f"/packages/{advisory}/items/{pending['id']}/decision",
                json={"role": role, "action": "approve"},
            )
        for conflict in (i for i in pkg["items"] if i["kind"] == "conflict"):
            client.post(
                f"/packages/{advisory}/items/{conflict['id']}/decision",
                json={"role": "director", "action": "defer", "reason": "stop-work"},
            )
        approved = client.post(
            f"/sitrep/{advisory}/approve", json={"role": "director", "text": "Situation report."}
        )
        assert approved.status_code == 200, approved.text
        assert package(client, advisory)["activation_level"] == "monitor"
    assert [
        e["type"] for e in client.get("/audit").json() if e["type"] == "activation_declared"
    ] == []
