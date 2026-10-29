"""GET /audit: newest first, filterable by actor, carrying scenario time and versions."""

from fastapi.testclient import TestClient


def test_audit_is_newest_first_and_filters_by_actor(client: TestClient) -> None:
    assert client.post("/advisories/next").status_code == 200
    pkg = client.get("/packages/1").json()
    review = next(i for i in pkg["items"] if i["rule_id"] == "P-4.1")
    client.post(
        f"/packages/1/items/{review['id']}/decision", json={"role": "planning", "action": "approve"}
    )

    events = client.get("/audit").json()
    by_actor = {
        actor: client.get("/audit", params={"actor": actor}).json()
        for actor in ("system", "agent", "human")
    }

    assert [e["id"] for e in events] == sorted((e["id"] for e in events), reverse=True)
    assert {e["actor"] for e in by_actor["system"]} == {"system"}
    assert [e["type"] for e in by_actor["agent"]] == ["sitrep_drafted"]
    assert by_actor["human"][0]["summary"] == "Planning approved P-4.1 for event"
    assert sum(len(v) for v in by_actor.values()) == len(events)


def test_audit_rejects_an_unknown_actor(client: TestClient) -> None:
    response = client.get("/audit", params={"actor": "robot"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_reset_leaves_only_the_reset_event(client: TestClient) -> None:
    client.post("/advisories/next")

    client.post("/advisories/reset")

    assert [e["type"] for e in client.get("/audit").json()] == ["scenario_reset"]


def test_decisions_and_not_decided_closures_carry_their_details(client: TestClient) -> None:
    client.post("/advisories/next")
    pkg = client.get("/packages/1").json()
    review = next(i for i in pkg["items"] if i["rule_id"] == "P-4.1")
    client.post(
        f"/packages/1/items/{review['id']}/decision", json={"role": "planning", "action": "approve"}
    )
    client.post("/advisories/next")

    events = client.get("/audit").json()
    decision = next(e for e in events if e["type"] == "decision")
    closed = next(e for e in events if e["type"] == "items_not_decided")

    assert (decision["payload"]["role"], decision["payload"]["action"]) == ("planning", "approve")
    assert {"rule_id", "entity_id"} <= set(closed["payload"]["items"][0])
    assert not any(i["rule_id"] == "P-4.1" for i in closed["payload"]["items"])
