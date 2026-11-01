"""The customers-out and field-demand forecast (ticket 38): known expected results on small
networks, then the forecast the advisory cycle stores and serves."""

import json
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from muster.challenger.dataset import load_world
from muster.config import REPO_ROOT
from muster.datagen.history import HISTORY_FILE
from muster.forecast.backtest import RESULTS_FILE, ForecastBacktest, run
from muster.forecast.model import (
    DistrictForecast,
    DistrictOutcome,
    ForecastAsset,
    forecast,
    outcome,
)
from muster.forecast.service import advisory_forecast
from muster.geo import FloatArray
from muster.ingest.contracts import SyntheticStormFile
from muster.models import Advisory, OutageForecast
from muster.models_config import load_models_config
from muster.planning.ics215 import usable_staging_areas
from muster.results_file import as_results
from muster.scoring_config import load_scoring_config
from tests.conftest import SeededScenario
from tests.test_demo_scenario import advance_to, scripted_decisions_at_advisory_3

CONFIG = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").forecast
MODELS = load_models_config(REPO_ROOT / "config" / "models.yaml")
DISTRICTS = ["West", "East"]

# Two districts. West: a substation feeding a pumping station, which feeds the treatment plant.
# East: a substation and a pumping station of its own.
ASSETS = [
    ForecastAsset("SUB-W", "substation", "West", 1000),
    ForecastAsset("PS-W", "pump_station", "West", 200),
    ForecastAsset("WTP", "treatment_plant", "West", 5000),
    ForecastAsset("SUB-E", "substation", "East", 3000),
    ForecastAsset("PS-E", "pump_station", "East", 400),
]
FED_BY = {"PS-W": ["SUB-W"], "WTP": ["PS-W"], "PS-E": ["SUB-E"]}
MEMBERS = 50


def probabilities(**p: float) -> FloatArray:
    """Members x assets, the same failure probability in every member unless spread is wanted."""
    return np.array([[p.get(a.id.replace("-", "_"), 0.0) for a in ASSETS]] * MEMBERS)


def spread(rng_seed: int = 0) -> FloatArray:
    """Failure probabilities that differ by member, as a real ensemble's do."""
    rng = np.random.default_rng(rng_seed)
    return rng.uniform(0.0, 0.8, size=(MEMBERS, len(ASSETS)))


def by_district[T: (DistrictForecast, DistrictOutcome)](result: list[T]) -> dict[str, T]:
    return {d.district: d for d in result}


def test_a_district_with_no_at_risk_assets_forecasts_zero() -> None:
    p = probabilities(SUB_W=0.6, PS_W=0.3, WTP=0.2)  # East: nothing at risk

    east = by_district(forecast(ASSETS, FED_BY, p, DISTRICTS, CONFIG, seed=1))["East"]

    for figure in (east.power_customers, east.water_customers, east.crews, east.generators):
        assert (figure.p50, figure.p90) == (0, 0)
    assert east.failed_assets.p90 == 0


def test_doubling_customers_served_doubles_customers_affected() -> None:
    p = spread()
    doubled = [replace(a, customers_served=2 * a.customers_served) for a in ASSETS]

    once = forecast(ASSETS, FED_BY, p, DISTRICTS, CONFIG, seed=7)
    twice = forecast(doubled, FED_BY, p, DISTRICTS, CONFIG, seed=7)

    for a, b in zip(once, twice, strict=True):
        assert b.power_customers.p50 == pytest.approx(2 * a.power_customers.p50)
        assert b.power_customers.p90 == pytest.approx(2 * a.power_customers.p90)
        assert b.water_customers.p50 == pytest.approx(2 * a.water_customers.p50)
        assert b.water_customers.p90 == pytest.approx(2 * a.water_customers.p90)
        assert b.crews == a.crews  # the field demand does not depend on customers


def test_p90_is_at_least_the_median() -> None:
    for seed in range(5):
        for d in forecast(ASSETS, FED_BY, spread(seed), DISTRICTS, CONFIG, seed=seed):
            for figure in (
                d.power_customers,
                d.water_customers,
                d.crews,
                d.generators,
                d.failed_assets,
            ):
                assert figure.p90 >= figure.p50


def test_the_forecast_is_deterministic_for_a_seed() -> None:
    p = spread()
    assert forecast(ASSETS, FED_BY, p, DISTRICTS, CONFIG, seed=3) == forecast(
        ASSETS, FED_BY, p, DISTRICTS, CONFIG, seed=3
    )


def test_power_and_water_customers_are_kept_separate() -> None:
    west = by_district(forecast(ASSETS, FED_BY, probabilities(SUB_W=1.0), DISTRICTS, CONFIG, 1))[
        "West"
    ]

    assert west.power_customers.p50 == 1000  # the failed substation's own customers
    # Its pumping station loses supply, and with it the only feeder of the treatment plant.
    assert west.water_customers.p50 == 200 + 5000


def test_water_customers_are_out_when_the_treatment_plant_loses_its_pumping_stations() -> None:
    west = by_district(forecast(ASSETS, FED_BY, probabilities(PS_W=1.0), DISTRICTS, CONFIG, 1))[
        "West"
    ]

    assert west.power_customers.p50 == 0
    assert west.water_customers.p50 == 200 + 5000


def test_field_demand_counts_repairs_and_generators_for_assets_out_of_supply() -> None:
    west = by_district(forecast(ASSETS, FED_BY, probabilities(SUB_W=1.0), DISTRICTS, CONFIG, 1))[
        "West"
    ]

    need = CONFIG.per_failed["substation"]
    lost = [CONFIG.per_supply_lost["pump_station"], CONFIG.per_supply_lost["treatment_plant"]]
    assert west.crews.p50 == need.crews + sum(n.crews for n in lost)
    assert west.generators.p50 == need.generators + sum(n.generators for n in lost)
    assert west.failed_assets.p50 == 1  # out of supply is not failed


def test_an_observed_outcome_is_aggregated_the_same_way() -> None:
    observed = by_district(
        outcome(ASSETS, FED_BY, {"SUB-E": True, "PS-W": True}, DISTRICTS, CONFIG)
    )
    certain = probabilities(SUB_E=1.0, PS_W=1.0)
    forecast_ = by_district(forecast(ASSETS, FED_BY, certain, DISTRICTS, CONFIG, seed=1))

    for name in DISTRICTS:
        o, f = observed[name], forecast_[name]
        assert (o.power_customers, o.water_customers) == (
            f.power_customers.p50,
            f.water_customers.p50,
        )
        assert (o.crews, o.generators, o.failed_assets) == (
            f.crews.p50,
            f.generators.p50,
            f.failed_assets.p50,
        )


# The forecast the advisory cycle stores and the API serves.


def get_forecast(client: TestClient, advisory: int) -> dict[str, Any]:
    response = client.get(f"/forecast?advisory={advisory}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_each_advisory_forecasts_every_district_west_to_east(client: TestClient) -> None:
    advance_to(client, 3)

    body = get_forecast(client, 3)

    assert [d["district"] for d in body["districts"]] == [
        "Westshore",
        "Bayport West",
        "Bayport East",
        "Eastern Plains",
    ]
    assert body["samples"] == 50 * CONFIG.draws
    shortfalls = [d["crews_short_p90"] for d in body["districts"]]
    assert shortfalls == [
        max(0, d["crews_needed"]["p90"] - d["crews_available"]) for d in body["districts"]
    ]
    assert any(shortfalls)  # the one rule the copilot and the screens show
    for d in body["districts"]:
        for figure in ("power_customers", "water_customers", "crews_needed", "generators_needed"):
            assert 0 <= d[figure]["p50"] <= d[figure]["p90"], (d["district"], figure)


def test_the_forecast_changes_with_each_advisory(client: TestClient) -> None:
    advance_to(client, 4)

    early, late = get_forecast(client, 1), get_forecast(client, 4)

    assert early["districts"] != late["districts"]
    total = sum(d["power_customers"]["p90"] for d in late["districts"])
    assert total > sum(d["power_customers"]["p90"] for d in early["districts"])


def test_the_forecast_is_the_same_after_a_reset(client: TestClient) -> None:
    advance_to(client, 2)
    first = get_forecast(client, 2)

    assert client.post("/advisories/reset").status_code == 200
    assert client.get("/forecast?advisory=1").status_code == 404
    advance_to(client, 2)

    assert get_forecast(client, 2) == first


def test_open_actions_add_their_field_demand_and_availability_follows_the_ics_215(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(3)
    planning = seeded.scoring.planning

    result = advisory_forecast(seeded.session, 3, seeded.playbook, planning)

    generators_for_actions = sum(d.generators_for_actions for d in result.districts)
    assert generators_for_actions > 0  # P-4.5: generators for the treatment plant's stations
    for d in result.districts:
        stored = seeded.session.get(OutageForecast, (3, d.district))
        assert stored is not None
        assert d.crews_needed.p50 == stored.crews_p50 + d.crews_for_actions
        assert d.generators_needed.p90 == stored.generators_p90 + d.generators_for_actions
    advisory = seeded.session.get(Advisory, 3)
    assert advisory is not None
    crews_per_area = sum(r.per_staging_area or 0 for r in planning.resources.values())
    usable = usable_staging_areas(seeded.session, advisory)
    assert sum(d.crews_available for d in result.districts) == crews_per_area * len(usable)
    assert result.generators_available == 6  # the fuelled fleet (gold initial state)


def test_an_advisory_not_yet_issued_has_no_forecast(client: TestClient) -> None:
    response = client.get("/forecast?advisory=2")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# The back-test on the synthetic history, Storm Delta held out.


def history() -> list[SyntheticStormFile]:
    return [SyntheticStormFile.model_validate(s) for s in json.loads(HISTORY_FILE.read_text())]


def backtest(seeded: SeededScenario, storms: list[SyntheticStormFile]) -> ForecastBacktest:
    world = load_world(seeded.session, seeded.scoring)
    return run(seeded.session, world, storms, seeded.scoring, MODELS.challenger)


def test_the_backtest_holds_storm_delta_out_and_reports_it_on_its_own(
    seeded: SeededScenario,
) -> None:
    report = backtest(seeded, history()[:2])

    assert report.held_out == "Storm Delta"
    assert "Storm Delta" not in report.history
    assert [(s.storm, s.held_out) for s in report.storms] == [
        ("Storm S01", False),
        ("Storm S02", False),
        ("Storm Delta", True),
    ]
    for metrics, storms in ((report.history_metrics, 2), (report.held_out_metrics, 1)):
        for m in metrics.values():
            assert m.cases == storms * 4  # every district of every storm
            assert 0 <= m.p90_coverage <= 1
    for storm in report.storms:
        for d in storm.districts:
            for figure in d.figures.values():
                assert figure.observed >= 0 and figure.p90 >= figure.p50 >= 0


def test_storm_delta_cannot_be_in_the_backtest_history(seeded: SeededScenario) -> None:
    storms = history()[:1]
    storms[0] = storms[0].model_copy(update={"name": "Storm Delta"})

    with pytest.raises(ValueError, match="held-out"):
        backtest(seeded, storms)


def test_the_committed_backtest_results_are_reproduced(seeded: SeededScenario) -> None:
    """make forecast-backtest wrote docs/eval/forecast_results.json from the same seeds."""
    report = backtest(seeded, history())

    committed = json.loads((REPO_ROOT / RESULTS_FILE).read_text())
    assert as_results(report) == committed


def test_the_demo_scene_at_advisory_3_shows_the_figures_the_script_names(
    client: TestClient,
) -> None:
    """docs/demo_script.md, scene 4 step 6: Bayport West after the scripted decisions."""
    scripted_decisions_at_advisory_3(client, inspect_ps14=False)

    west = next(d for d in get_forecast(client, 3)["districts"] if d["district"] == "Bayport West")

    def thousands(figure: dict[str, float]) -> tuple[int, int]:
        return round(figure["p50"] / 1000), round(figure["p90"] / 1000)

    assert thousands(west["power_customers"]) == (27, 113)
    assert thousands(west["water_customers"]) == (6, 115)
    assert (west["crews_needed"]["p50"], west["crews_needed"]["p90"]) == (14, 47)
    assert west["crews_available"] == 8
