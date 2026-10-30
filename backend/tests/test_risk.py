"""Seam 2 (risk properties the plan's M3 requires), the explanation, alerts and the seed check."""

from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from muster.config import REPO_ROOT
from muster.datagen.seed_check import check_seeds
from muster.risk.fragility import adjusted_theta, combine, failure_probability
from muster.scoring_config import load_scoring_config

CONFIG = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
STEP = CONFIG.risk.condition_theta_reduction_per_step


def test_failure_probability_stays_between_0_and_1() -> None:
    p = failure_probability(np.array([0.0, 1.0, 80.0, 140.0, 200.0, 1e6]), 140.0, 0.25)

    assert np.all((p >= 0) & (p <= 1))
    assert p[0] == 0.0


def test_failure_probability_rises_with_exposure() -> None:
    p = failure_probability(np.linspace(1.0, 250.0, 100), 140.0, 0.25)

    assert np.all(np.diff(p) >= 0)
    assert failure_probability(np.array([140.0]), 140.0, 0.25)[0] == pytest.approx(0.5)


def test_poorer_condition_never_lowers_p_fail() -> None:
    wind = np.array([60.0, 100.0, 130.0, 160.0])
    by_condition = [
        failure_probability(wind, adjusted_theta(140.0, c, STEP), 0.25) for c in range(1, 6)
    ]

    assert all(
        np.all(worse >= better)
        for better, worse in zip(by_condition, by_condition[1:], strict=False)
    )
    assert adjusted_theta(140.0, 5, STEP) == pytest.approx(140.0 * 0.7)


def test_either_hazard_can_fail_the_asset() -> None:
    assert combine(np.array([0.2]), np.array([0.5]))[0] == pytest.approx(0.6)


def advance_to(client: TestClient, advisory: int) -> None:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200


def top10(client: TestClient, advisory: int) -> set[str]:
    items = client.get("/risk", params={"advisory": advisory}).json()["items"]
    return {i["asset_id"] for i in items if i["rank"] <= 10}


def test_top_10_changes_between_advisories_2_and_4(client: TestClient) -> None:
    advance_to(client, 4)

    assert top10(client, 2) != top10(client, 4)


def test_explanation_factors_reproduce_the_stored_risk(client: TestClient) -> None:
    advance_to(client, 3)
    items = client.get("/risk", params={"advisory": 3}).json()["items"]

    for item in items[:15]:
        body = client.get(f"/assets/{item['asset_id']}/explain", params={"advisory": 3}).json()
        consequence = body["consequence"]
        total = (
            consequence["own_customers"]
            + sum(a["customers"] for a in consequence["downstream_assets"])
            + sum(f["weight"] for f in consequence["facilities"])
        )
        assert total == pytest.approx(consequence["total"])
        assert body["p_fail"] * consequence["total"] == pytest.approx(item["risk"])
        assert body["rank"] == item["rank"]


def test_explanation_shows_fragility_condition_and_dependencies(client: TestClient) -> None:
    advance_to(client, 3)

    body = client.get("/assets/SUB-07/explain", params={"advisory": 3}).json()

    assert body["asset"]["condition_score"] == 5
    assert body["wind"]["theta_adjusted"] == pytest.approx(body["wind"]["theta"] * (1 - 4 * STEP))
    assert {"id": "HOSP-01", "kind": "facility", "name": "Bayport General Hospital"} in body[
        "feeds"
    ]
    assert body["exposure"]["site_id"] == "SUB-07"
    hospital = next(f for f in body["consequence"]["facilities"] if f["id"] == "HOSP-01")
    assert hospital["weight"] == CONFIG.consequence_weights["hospital"]


def test_confidence_drops_for_imputed_elevation_and_stale_inspection(client: TestClient) -> None:
    advance_to(client, 1)

    def explain(asset: str) -> dict[str, Any]:
        result: dict[str, Any] = client.get(
            f"/assets/{asset}/explain", params={"advisory": 1}
        ).json()
        return result

    assert explain("SUB-15")["confidence"] == "low"
    assert explain("SUB-22")["confidence"] == "medium"
    assert "inspection" in explain("SUB-22")["confidence_reasons"][0]
    assert explain("SUB-07")["confidence"] == "high"


def test_explanation_errors(client: TestClient) -> None:
    advance_to(client, 1)

    unknown = client.get("/assets/SUB-999/explain", params={"advisory": 1})
    not_issued = client.get("/assets/SUB-07/explain", params={"advisory": 2})

    assert unknown.status_code == 404
    assert not_issued.status_code == 404
    assert not_issued.json()["error"]["code"] == "not_found"


def test_alerts_follow_the_rules(client: TestClient) -> None:
    advance_to(client, 5)
    threshold = CONFIG.risk.alert.risk_threshold

    first = client.get("/alerts", params={"advisory": 1}).json()
    later = [a for n in range(2, 6) for a in client.get("/alerts", params={"advisory": n}).json()]

    assert all(a["kind"] == "risk_threshold" for a in first), "the top 10 is initial at advisory 1"
    assert any(a["kind"] == "risk_threshold" for a in later)
    for n in range(2, 6):
        risk = {
            i["asset_id"]: i for i in client.get("/risk", params={"advisory": n}).json()["items"]
        }
        for alert in client.get("/alerts", params={"advisory": n}).json():
            item = risk[alert["asset_id"]]
            if alert["kind"] == "risk_threshold":
                assert item["risk"] >= threshold
            elif alert["kind"] == "top_n_entry":
                assert item["rank"] <= 10 < item["previous_rank"]
            else:
                assert item["previous_rank"] - item["rank"] >= 10


def test_alerts_for_an_advisory_not_yet_issued_are_not_found(client: TestClient) -> None:
    assert client.get("/alerts", params={"advisory": 1}).status_code == 404


def test_every_demo_seed_fact_holds() -> None:
    assert check_seeds(REPO_ROOT / "data" / "gold", CONFIG) == []
