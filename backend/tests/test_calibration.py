"""Calibration (plan M8, CR-01 C6): the Storm Delta back-test, the MAP fit and model versions."""

import json
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.calibration.backtest import Observation, brier_score, predict, reliability, top_capture
from app.calibration.fit import fit_map
from app.config import REPO_ROOT
from app.datagen.generate import FRAGILITY_CURVES, TRUE_FRAGILITY_CURVES
from app.models import FragilityCurve
from app.scoring_config import load_scoring_config

CONFIG = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
STEP = CONFIG.risk.condition_theta_reduction_per_step


def gold(name: str) -> Any:
    return json.loads((REPO_ROOT / "data" / "gold" / name).read_text())


def test_brier_score_is_the_mean_squared_error_of_the_probabilities() -> None:
    p = np.array([0.0, 1.0, 0.5, 0.2])
    failed = np.array([False, True, True, False])

    assert brier_score(p, failed) == pytest.approx((0 + 0 + 0.25 + 0.04) / 4)


def test_reliability_has_ten_bins_with_mean_prediction_and_observed_rate() -> None:
    p = np.array([0.05, 0.05, 0.15, 0.95, 1.0])
    failed = np.array([False, True, False, True, True])

    bins = reliability(p, failed, 10)

    assert len(bins) == 10
    assert (bins[0].lower, bins[0].upper) == (0.0, 0.1)
    assert (bins[0].count, bins[0].mean_predicted, bins[0].observed_rate) == (2, 0.05, 0.5)
    assert (bins[1].count, bins[1].observed_rate) == (1, 0.0)
    assert (bins[5].count, bins[5].mean_predicted, bins[5].observed_rate) == (0, None, None)
    assert bins[9].count == 2  # a probability of 1 falls in the last bin
    assert sum(b.count for b in bins) == len(p)


def test_top_capture_is_the_share_of_failures_in_the_highest_predicted_tenth() -> None:
    p = np.linspace(0.0, 1.0, 20)  # the top tenth is the two highest
    failed = np.zeros(20, dtype=bool)
    failed[[19, 5, 3, 1]] = True

    assert top_capture(p, failed, 0.10) == pytest.approx(1 / 4)


def test_top_capture_without_failures_is_zero() -> None:
    assert top_capture(np.array([0.1, 0.9]), np.array([False, False]), 0.5) == 0.0


PRIOR = [
    FragilityCurve(asset_type="substation", hazard="wind", theta=140.0, beta=0.25),
    FragilityCurve(asset_type="substation", hazard="flood", theta=0.8, beta=0.5),
]
TRUTH = [
    FragilityCurve(asset_type="substation", hazard="wind", theta=140.0 / 1.2, beta=0.25),
    FragilityCurve(asset_type="substation", hazard="flood", theta=0.8 / 1.2, beta=0.5),
]


def storm_outcomes(n: int, seed: int) -> list[Observation]:
    """Exposures across the fragility range, with failures drawn from the true curves."""
    rng = np.random.default_rng(seed)
    exposed = [
        Observation(f"SUB-{i:03d}", "substation", int(c), float(w), float(f), False)
        for i, (w, f, c) in enumerate(
            zip(
                rng.uniform(60, 180, n),
                np.where(rng.random(n) < 0.4, rng.uniform(0, 2, n), 0.0),
                rng.integers(1, 6, n),
                strict=True,
            )
        )
    ]
    p_true = predict(exposed, TRUTH, STEP)
    return [
        replace(o, failed=bool(u < p))
        for o, u, p in zip(exposed, rng.random(n), p_true, strict=True)
    ]


def test_map_fit_moves_the_curves_towards_the_truth_and_lowers_the_brier_score() -> None:
    observations = storm_outcomes(400, seed=7)
    failed = np.array([o.failed for o in observations])

    fitted = fit_map(observations, PRIOR, STEP, prior_sd_log_theta=0.25, prior_sd_log_beta=0.25)

    by_key = {(c.asset_type, c.hazard): c for c in fitted}
    for truth, prior in zip(TRUTH, PRIOR, strict=True):
        theta = by_key[(truth.asset_type, truth.hazard)].theta
        assert abs(theta - truth.theta) < abs(prior.theta - truth.theta)
    before = brier_score(predict(observations, PRIOR, STEP), failed)
    after = brier_score(predict(observations, fitted, STEP), failed)
    assert after < before


def test_a_tight_prior_keeps_the_fit_near_the_prior() -> None:
    observations = storm_outcomes(400, seed=7)

    fitted = fit_map(observations, PRIOR, STEP, prior_sd_log_theta=0.001, prior_sd_log_beta=0.001)

    for curve, prior in zip(fitted, PRIOR, strict=True):
        assert curve.theta == pytest.approx(prior.theta, rel=0.01)
        assert curve.beta == pytest.approx(prior.beta, rel=0.01)


def run_calibration(client: TestClient) -> dict[str, Any]:
    response = client.post("/calibration/run")
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def approve(client: TestClient, version_id: int, role: str) -> Any:
    return client.post(f"/model-versions/{version_id}/approve", json={"role": role})


def p_fail_at_advisory_1(client: TestClient) -> tuple[int, dict[str, float]]:
    assert client.post("/advisories/next").status_code == 200
    risk = client.get("/risk", params={"advisory": 1}).json()
    return risk["model_version"], {i["asset_id"]: i["p_fail"] for i in risk["items"]}


def test_calibration_back_tests_storm_delta_before_and_after_and_proposes_a_version(
    client: TestClient,
) -> None:
    result = run_calibration(client)

    assert result["storm"] == "Storm Delta"
    before, after = result["before"], result["after"]
    for metrics in (before, after):
        assert metrics["assets"] == 196
        assert metrics["failures"] > 0
        assert len(metrics["reliability"]) == 10
        assert sum(b["count"] for b in metrics["reliability"]) == 196
        assert 0 <= metrics["top_capture"] <= 1
        assert metrics["top_fraction"] == CONFIG.calibration.top_fraction
    assert after["brier"] < before["brier"]
    assert before["model_version"] == 1
    version = result["model_version"]
    assert (version["kind"], version["status"], version["approved_by"]) == (
        "curves",
        "proposed",
        None,
    )
    assert len(version["curves"]) == 6
    listed = {v["id"]: v for v in client.get("/model-versions").json()}
    assert version["id"] > 1 and listed[version["id"]]["status"] == "proposed"
    assert listed[1]["status"] == "approved"


def test_the_fit_moves_the_published_medians_down_towards_the_true_capacities(
    client: TestClient,
) -> None:
    curves = run_calibration(client)["model_version"]["curves"]
    published = {(c["asset_type"], c["hazard"]): c for c in gold("fragility_curves.json")}

    for c in curves:
        if c["asset_type"] != "treatment_plant" and c["hazard"] == "wind":
            assert c["theta"] < published[(c["asset_type"], "wind")]["theta"]


def test_an_unapproved_version_is_never_used_for_scoring(client: TestClient) -> None:
    run_calibration(client)

    version, _ = p_fail_at_advisory_1(client)

    assert version == 1


def test_an_approved_version_scores_the_next_replay_and_changes_the_scores(
    client: TestClient,
) -> None:
    version_1, p_fail_1 = p_fail_at_advisory_1(client)
    proposed = run_calibration(client)["model_version"]["id"]
    assert approve(client, proposed, "planning").status_code == 200
    assert client.post("/advisories/reset").status_code == 200

    version_2, p_fail_2 = p_fail_at_advisory_1(client)

    assert (version_1, version_2) == (1, proposed)
    assert p_fail_1 != p_fail_2
    assert sum(p_fail_2.values()) > sum(p_fail_1.values())  # lower capacities, more failures


def test_approval_is_by_role_and_the_audit_log_shows_who_approved(client: TestClient) -> None:
    proposed = run_calibration(client)["model_version"]["id"]

    refused = approve(client, proposed, "operations")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "decision_refused"
    listed = {v["id"]: v for v in client.get("/model-versions").json()}
    assert listed[proposed]["status"] == "proposed"

    response = approve(client, proposed, "planning")
    assert response.status_code == 200
    approved = response.json()
    assert (approved["status"], approved["approved_by"]) == ("approved", "planning")
    assert approved["approved_at"] is not None

    assert client.post("/advisories/reset").status_code == 200  # survives a scenario reset
    events = client.get("/audit", params={"actor": "human"}).json()
    event = next(e for e in events if e["type"] == "model_version_approved")
    assert event["payload"]["model_version"] == proposed
    assert event["payload"]["approved_by"] == "planning"
    assert "planning" in event["summary"].lower()
    runs = [e for e in client.get("/audit").json() if e["type"] == "calibration_run"]
    assert len(runs) == 1


def test_a_version_is_approved_once(client: TestClient) -> None:
    proposed = run_calibration(client)["model_version"]["id"]
    assert approve(client, proposed, "director").status_code == 200

    again = approve(client, proposed, "planning")

    assert again.status_code == 409
    assert approve(client, 1, "planning").status_code == 409  # the published curves


def test_a_role_that_may_not_approve_is_refused_even_on_an_approved_version(
    client: TestClient,
) -> None:
    response = approve(client, 1, "logistics")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "decision_refused"


def test_approving_an_unknown_version_is_not_found(client: TestClient) -> None:
    response = approve(client, 99, "planning")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_the_package_audit_records_the_model_version_that_scored_the_advisory(
    client: TestClient,
) -> None:
    proposed = run_calibration(client)["model_version"]["id"]
    approve(client, proposed, "planning")
    client.post("/advisories/next")

    events = [e for e in client.get("/audit").json() if e["advisory_no"] == 1]

    assert events
    assert all(e["versions"]["model_version"] == proposed for e in events if e["versions"])


def test_the_true_curves_are_about_20_percent_below_the_published_ones() -> None:
    published = {(c["asset_type"], c["hazard"]): c["theta"] for c in FRAGILITY_CURVES}

    for c in TRUE_FRAGILITY_CURVES:
        assert published[(c["asset_type"], c["hazard"])] / c["theta"] == pytest.approx(
            1.2, rel=0.01
        )
