from typing import Any

import pytest
from fastapi.testclient import TestClient


def advance(client: TestClient, times: int) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for _ in range(times):
        response = client.post("/advisories/next")
        assert response.status_code == 200
        body = response.json()
    return body


def test_scenario_starts_before_advisory_1(client: TestClient) -> None:
    body = client.get("/advisories").json()

    assert body["current_advisory"] == 0
    assert body["total_advisories"] == 5
    assert body["advisories"] == []


def test_first_advisory_is_72_hours_out_at_prepare(client: TestClient) -> None:
    body = advance(client, 1)

    assert body["current_advisory"] == 1
    latest = body["advisories"][-1]
    assert latest["hours_to_landfall"] == 72
    assert latest["activation_level"] == "prepare"


def test_third_advisory_is_48_hours_out_at_full_activation(client: TestClient) -> None:
    body = advance(client, 3)

    assert [a["hours_to_landfall"] for a in body["advisories"]] == [72, 60, 48]
    assert body["advisories"][-1]["activation_level"] == "full"


def test_advancing_past_the_last_advisory_is_refused(client: TestClient) -> None:
    advance(client, 5)

    response = client.post("/advisories/next")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "scenario_complete"
    assert client.get("/advisories").json()["current_advisory"] == 5


def test_reset_returns_to_before_advisory_1(client: TestClient) -> None:
    advance(client, 3)

    body = client.post("/advisories/reset").json()

    assert body["current_advisory"] == 0
    assert body["advisories"] == []
    assert client.get("/risk", params={"advisory": 1}).status_code == 404


def test_risk_list_ranks_every_asset_for_an_issued_advisory(client: TestClient) -> None:
    advance(client, 1)
    asset_ids = {a["id"] for a in client.get("/assets").json()}

    body = client.get("/risk", params={"advisory": 1}).json()

    assert body["advisory_no"] == 1
    assert {item["asset_id"] for item in body["items"]} == asset_ids
    assert [item["rank"] for item in body["items"]] == list(range(1, len(asset_ids) + 1))
    risks = [item["risk"] for item in body["items"]]
    assert risks == sorted(risks, reverse=True)


def test_risk_for_an_advisory_not_yet_issued_is_not_found(client: TestClient) -> None:
    advance(client, 1)

    response = client.get("/risk", params={"advisory": 2})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_risk_without_an_advisory_number_is_a_validation_error(client: TestClient) -> None:
    response = client.get("/risk")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_coastline_has_a_line_and_a_land_polygon(client: TestClient) -> None:
    body = client.get("/coastline").json()

    assert len(body["coastline"]) > 2
    assert len(body["land"]) > 2
    assert set(body["coastline"][0]) == {"x_km", "y_km"}


def test_timeline_lists_every_advisory_with_its_hours_and_level(client: TestClient) -> None:
    body = advance(client, 2)

    timeline = body["timeline"]
    assert [slot["hours_to_landfall"] for slot in timeline] == [72, 60, 48, 36, 24]
    assert [slot["activation_level"] for slot in timeline] == [
        "prepare",
        "prepare",
        "full",
        "full",
        "full",
    ]
    assert [slot["issued"] for slot in timeline] == [True, True, False, False, False]


def test_issued_advisory_reports_max_wind_and_peak_surge(client: TestClient) -> None:
    latest = advance(client, 1)["advisories"][-1]

    assert latest["max_wind_mph"] == 130
    assert latest["peak_surge_m"] == 2.5


def test_changes_at_advisory_1_are_initial(client: TestClient) -> None:
    advance(client, 1)

    body = client.get("/advisories/1/changes").json()

    assert body["previous_advisory_no"] is None
    assert body["landfall_shift"] is None
    assert body["rank_moves"] == []
    assert len(body["top10_entered"]) == 0


def test_changes_at_advisory_3_show_the_eastward_shift_and_full_activation(
    client: TestClient,
) -> None:
    advance(client, 3)

    body = client.get("/advisories/3/changes").json()

    assert body["previous_advisory_no"] == 2
    assert body["landfall_shift"]["direction"] == "east"
    # About 40 km east along a curved coast (docs/decisions.md).
    assert body["landfall_shift"]["distance_km"] == pytest.approx(40, abs=5)
    assert body["max_wind_change_mph"] == 5
    assert body["peak_surge_change_m"] == 0.5
    assert body["activation_level_from"] == "prepare"
    assert body["activation_level_to"] == "full"
    moves = body["rank_moves"]
    assert moves, "the eastward shift reorders the list"
    assert all(m["from_rank"] != m["to_rank"] for m in moves)
    biggest = [abs(m["from_rank"] - m["to_rank"]) for m in moves]
    assert biggest == sorted(biggest, reverse=True)


def test_changes_for_an_advisory_not_yet_issued_are_not_found(client: TestClient) -> None:
    response = client.get("/advisories/1/changes")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_risk_rows_carry_the_previous_rank(client: TestClient) -> None:
    advance(client, 1)
    first = client.get("/risk", params={"advisory": 1}).json()["items"]
    advance(client, 2)

    third = client.get("/risk", params={"advisory": 3}).json()["items"]
    second = {
        i["asset_id"]: i["rank"]
        for i in client.get("/risk", params={"advisory": 2}).json()["items"]
    }

    assert all(item["previous_rank"] is None for item in first)
    assert all(item["previous_rank"] == second[item["asset_id"]] for item in third)
