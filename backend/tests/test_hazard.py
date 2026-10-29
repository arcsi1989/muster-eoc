"""Seam 2 (hazard properties the plan's M2 requires) and the hazard-dependent demo seeds."""

from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.hazard.ensemble import Site, StormInput, compute_exposure
from app.hazard.surge import flood_depth, local_surge
from app.hazard.wind import rankine_wind
from app.scoring_config import load_scoring_config

CONFIG = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").hazard


def test_wind_equals_vmax_at_rmax() -> None:
    assert rankine_wind(np.array([37.0]), 145.0, 37.0, CONFIG.wind.alpha)[0] == pytest.approx(145.0)


def test_wind_decays_monotonically_beyond_rmax() -> None:
    r = np.linspace(37.0, 600.0, 200)

    wind = rankine_wind(r, 145.0, 37.0, CONFIG.wind.alpha)

    assert np.all(np.diff(wind) < 0)


def test_wind_rises_towards_rmax_inside_the_eye() -> None:
    wind = rankine_wind(np.array([0.0, 10.0, 20.0, 36.0]), 145.0, 37.0, CONFIG.wind.alpha)

    assert np.all(np.diff(wind) > 0)


def test_flood_depth_is_zero_where_ground_is_above_the_surge() -> None:
    depth = flood_depth(np.array([1.5, 1.5, 1.5]), np.array([1.0, 1.5, 3.0]))

    assert depth.tolist() == [0.5, 0.0, 0.0]


def test_surge_falls_away_from_landfall_and_inland() -> None:
    at_landfall = local_surge(4.0, np.array([0.0]), np.array([0.0]), 37.0, 3.0)[0]
    along = local_surge(4.0, np.array([50.0]), np.array([0.0]), 37.0, 3.0)[0]
    inland = local_surge(4.0, np.array([0.0]), np.array([5.0]), 37.0, 3.0)[0]

    assert at_landfall == pytest.approx(4.0)
    assert along < at_landfall
    assert inland < at_landfall


def storm_and_sites() -> tuple[
    StormInput, list[Site], list[tuple[float, float]], list[tuple[float, float]]
]:
    track: list[dict[str, Any]] = [
        {
            "t_hours": float(t),
            "x_km": 100.0,
            "y_km": 50.0 + 14.0 * (t - 24),
            "vmax_mph": 140.0,
            "rmax_km": 37.0,
        }
        for t in range(0, 49, 6)
    ]
    coast = [(0.0, 50.0), (200.0, 50.0)]
    land = [(0.0, 50.0), (200.0, 50.0), (200.0, 300.0), (0.0, 300.0)]
    storm = StormInput(1, 24, track, {"24": 72.0, "48": 124.0}, (100.0, 50.0), 3.5)
    sites = [
        Site(f"S{i}", "asset", 60.0 + 10 * i, 51.0 + 3 * i, 0.5 + 0.3 * i, False, 1.0 + 3 * i)
        for i in range(8)
    ]
    return storm, sites, coast, land


def test_p90_is_never_below_p50() -> None:
    exposures = compute_exposure(*storm_and_sites(), CONFIG)

    assert all(e.wind_p90_mph >= e.wind_p50_mph for e in exposures)
    assert all(e.flood_depth_p90_m >= e.flood_depth_p50_m for e in exposures)


def test_same_seed_gives_the_same_numbers() -> None:
    first = compute_exposure(*storm_and_sites(), CONFIG)
    second = compute_exposure(*storm_and_sites(), CONFIG)

    assert [(e.wind_p50_mph, e.flood_depth_p90_m, e.tsforce_arrival_h) for e in first] == [
        (e.wind_p50_mph, e.flood_depth_p90_m, e.tsforce_arrival_h) for e in second
    ]


def test_cross_track_spread_scales_with_the_cone_factor() -> None:
    def wind_spread(factor: float) -> float:
        ensemble = CONFIG.ensemble.model_copy(update={"sigma_cone_factor": factor})
        config = CONFIG.model_copy(update={"ensemble": ensemble})
        exposures = compute_exposure(*storm_and_sites(), config)
        return float(np.mean([np.std(e.wind_members_mph) for e in exposures]))

    none, narrow, configured, wide = (
        wind_spread(f) for f in (0.0, 0.5, CONFIG.ensemble.sigma_cone_factor, 2.0)
    )

    assert none == pytest.approx(0.0)
    assert narrow < configured < wide


def exposure_at(client: TestClient, advisory: int) -> dict[str, dict[str, Any]]:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200
    return {e["site_id"]: e for e in client.get("/exposure", params={"advisory": advisory}).json()}


def test_exposure_covers_every_asset_and_staging_area(client: TestClient) -> None:
    exposure = exposure_at(client, 1)

    assert len([e for e in exposure.values() if e["site_kind"] == "asset"]) == 196
    assert len([e for e in exposure.values() if e["site_kind"] == "staging_area"]) == 5
    assert {k for k, e in exposure.items() if e["elevation_imputed"]} == {
        "SUB-15",
        "SUB-44",
        "PS-27",
    }


def test_exposure_for_an_advisory_not_yet_issued_is_not_found(client: TestClient) -> None:
    response = client.get("/exposure", params={"advisory": 1})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_issued_advisory_carries_its_forecast_cone(client: TestClient) -> None:
    advisory = client.post("/advisories/next").json()["advisories"][-1]

    assert len(advisory["cone"]) == 2 * len(advisory["track"])


# Demo seeds that depend on hazard only (plan section 2.2; the risk ones follow in ticket 04).


def test_ps_14_floods_above_half_a_metre_from_advisory_3(client: TestClient) -> None:
    assert all(exposure_at(client, n)["PS-14"]["flood_depth_p90_m"] > 0.5 for n in (3, 4, 5))


def test_stop_work_wind_reaches_ps_14_within_12_hours_only_at_advisory_5(
    client: TestClient,
) -> None:
    arrivals = {n: exposure_at(client, n)["PS-14"]["tsforce_arrival_h"] for n in (3, 4, 5)}

    assert arrivals[3] > 12
    assert arrivals[4] > 12
    assert arrivals[5] <= 12


def test_stg_02_floods_from_advisory_4(client: TestClient) -> None:
    floods = {n: exposure_at(client, n)["STG-02"]["flood_depth_p90_m"] for n in range(1, 6)}

    assert [floods[n] > 0 for n in range(1, 6)] == [False, False, False, True, True]
    others = exposure_at(client, 5)
    assert all(
        others[s]["flood_depth_p90_m"] == 0 for s in ("STG-01", "STG-03", "STG-04", "STG-05")
    )
