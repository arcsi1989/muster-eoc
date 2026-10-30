"""CR-02 C1: what the storm map draws for an advisory (track with intensity, past positions,
NHC-style cone), and that issuing an advisory stays fast."""

import json
import time
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pytest
import shapely
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import REPO_ROOT
from app.hazard.ensemble import StormInput, track_shift_sd
from app.hazard.track import cone_circles, cone_polygon, intensity_category
from app.risk.bands import risk_band, top_factor
from app.scoring_config import IntensityCategory, RiskBand, RiskConfig, load_scoring_config

CONFIG = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").hazard
ADVISORIES = [
    json.loads(path.read_text())
    for path in sorted((REPO_ROOT / "data" / "gold" / "advisories").glob("adv_*.json"))
]


@pytest.mark.parametrize(
    ("wind_mph", "category"),
    [
        (38.0, "tropical_depression"),
        (39.0, "tropical_storm"),
        (73.0, "tropical_storm"),
        (74.0, "cat_1"),
        (95.0, "cat_1"),
        (96.0, "cat_2"),
        (110.0, "cat_2"),
        (111.0, "cat_3"),
        (129.0, "cat_3"),
        (130.0, "cat_4"),
        (156.0, "cat_4"),
        (157.0, "cat_5"),
        (190.0, "cat_5"),
    ],
)
def test_saffir_simpson_category_at_each_boundary(wind_mph: float, category: str) -> None:
    assert intensity_category(wind_mph, CONFIG.intensity_min_mph) == category


def test_category_thresholds_come_from_config() -> None:
    thresholds: dict[IntensityCategory, float] = {"tropical_depression": 0.0, "cat_5": 100.0}

    assert intensity_category(99.0, thresholds) == "tropical_depression"
    assert intensity_category(100.0, thresholds) == "cat_5"


def storm(advisory: dict[str, Any]) -> StormInput:
    landfall = (advisory["landfall"]["x_km"], advisory["landfall"]["y_km"])
    return StormInput(
        advisory["advisory_no"],
        advisory["hours_to_landfall"],
        advisory["track"],
        advisory["cone_radius_km"],
        landfall,
        advisory["peak_surge_m"],
    )


@pytest.mark.parametrize("advisory", ADVISORIES, ids=lambda a: f"adv_{a['advisory_no']}")
def test_cone_and_ensemble_read_the_same_cone_radius(advisory: dict[str, Any]) -> None:
    circles = cone_circles(advisory["track"], advisory["cone_radius_km"])
    at_landfall = next(
        c.radius_km
        for c, p in zip(circles, advisory["track"], strict=True)
        if p["t_hours"] == advisory["hours_to_landfall"]
    )

    published = {0.0: 0.0, **{float(k): v for k, v in advisory["cone_radius_km"].items()}}
    for circle, point in zip(circles, advisory["track"], strict=True):
        if point["t_hours"] in published:  # between published lead times it is interpolated
            assert circle.radius_km == published[point["t_hours"]]
    assert track_shift_sd(storm(advisory), CONFIG.ensemble) == pytest.approx(
        CONFIG.ensemble.sigma_cone_factor * at_landfall
    )


def width_across_track(cone: shapely.Polygon, point: dict[str, Any], heading: np.ndarray) -> float:
    normal = np.array([-heading[1], heading[0]]) * 2000.0
    centre = np.array([point["x_km"], point["y_km"]])
    return float(cone.intersection(shapely.LineString([centre - normal, centre + normal])).length)


@pytest.mark.parametrize("advisory", ADVISORIES, ids=lambda a: f"adv_{a['advisory_no']}")
def test_cone_widens_with_lead_time(advisory: dict[str, Any]) -> None:
    track = advisory["track"]
    cone = shapely.Polygon(cone_polygon(track, advisory["cone_radius_km"]))
    first, last = track[0], track[-1]
    heading = np.array([last["x_km"] - first["x_km"], last["y_km"] - first["y_km"]])
    heading /= np.linalg.norm(heading)

    widths = [width_across_track(cone, p, heading) for p in track[1:]]

    assert cone.is_valid
    assert np.all(np.diff(widths) > 0)


def test_cone_is_the_union_of_hulls_of_consecutive_circles() -> None:
    advisory = ADVISORIES[2]
    circles = cone_circles(advisory["track"], advisory["cone_radius_km"])
    cone = shapely.Polygon(cone_polygon(advisory["track"], advisory["cone_radius_km"]))

    for c in circles[1:]:
        assert cone.buffer(0.01).contains(shapely.Point(c.x_km, c.y_km).buffer(c.radius_km))
    assert len(cone.interiors) == 0
    assert len(cone.exterior.coords) > 2 * len(advisory["track"])  # not the old side-offset outline


def advance_to(client: TestClient, advisory_no: int) -> dict[str, Any]:
    scenario: dict[str, Any] = client.get("/advisories").json()
    while scenario["current_advisory"] < advisory_no:
        response = client.post("/advisories/next")
        assert response.status_code == 200
        scenario = response.json()
    return scenario


def test_forecast_points_carry_time_wind_and_category(client: TestClient) -> None:
    advisory = advance_to(client, 1)["advisories"][0]
    issued = datetime.fromisoformat(advisory["issued_at"])

    point = advisory["track"][2]

    assert datetime.fromisoformat(point["valid_at"]) == issued + timedelta(hours=point["t_hours"])
    assert point["vmax_mph"] == 130.0
    assert point["category"] == "cat_4"


def test_past_positions_are_the_earlier_advisories_at_issue(client: TestClient) -> None:
    advisories = advance_to(client, 3)["advisories"]

    past = advisories[2]["past_positions"]

    assert advisories[0]["past_positions"] == []
    assert [p["advisory_no"] for p in past] == [1, 2]
    for p, earlier in zip(past, advisories, strict=False):
        start = earlier["track"][0]
        assert (p["x_km"], p["y_km"], p["vmax_mph"]) == (
            start["x_km"],
            start["y_km"],
            start["vmax_mph"],
        )
        assert p["valid_at"] == earlier["issued_at"]
        assert p["category"] == start["category"]


def test_issued_advisory_carries_the_nhc_style_cone(client: TestClient) -> None:
    advisory = advance_to(client, 1)["advisories"][0]
    cone = shapely.Polygon([(p["x_km"], p["y_km"]) for p in advisory["cone"]])

    assert cone.is_valid
    assert all(
        cone.buffer(0.01).contains(shapely.Point(p["x_km"], p["y_km"])) for p in advisory["track"]
    )


def test_issuing_each_advisory_takes_under_two_seconds(client: TestClient) -> None:
    for _ in range(5):
        start = time.perf_counter()
        response = client.post("/advisories/next")
        elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < 2.0


@pytest.mark.parametrize(
    ("p_fail", "band"),
    [
        (0.0, "low"),
        (0.099, "low"),
        (0.1, "moderate"),
        (0.249, "moderate"),
        (0.25, "high"),
        (0.399, "high"),
        (0.4, "severe"),
        (1.0, "severe"),
    ],
)
def test_risk_band_at_each_boundary(p_fail: float, band: str) -> None:
    thresholds: dict[RiskBand, float] = {"low": 0, "moderate": 0.1, "high": 0.25, "severe": 0.4}

    assert risk_band(p_fail, thresholds) == band


def test_risk_band_thresholds_come_from_config() -> None:
    config = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").risk.band_min_p_fail

    assert risk_band(config["severe"], config) == "severe"
    assert risk_band(config["severe"] - 0.001, config) == "high"


@pytest.mark.parametrize(
    "bands",
    [
        {"moderate": 0.1, "high": 0.25, "severe": 0.4},
        {"low": 0.05, "moderate": 0.1, "high": 0.25, "severe": 0.4},
        {"low": 0, "moderate": 0.3, "high": 0.25, "severe": 0.4},
    ],
)
def test_risk_bands_need_every_band_rising_from_zero(bands: dict[str, float]) -> None:
    raw = yaml.safe_load((REPO_ROOT / "config" / "scoring.yaml").read_text())
    raw["risk"]["band_min_p_fail"] = bands

    with pytest.raises(ValidationError, match="rising thresholds from 0"):
        RiskConfig.model_validate(raw["risk"])


@pytest.mark.parametrize(
    ("p_wind", "p_flood", "factor"),
    [(0.3, 0.1, "wind"), (0.1, 0.3, "flood"), (0.2, 0.2, "wind")],
)
def test_top_factor_is_the_hazard_with_the_higher_p_fail(
    p_wind: float, p_flood: float, factor: str
) -> None:
    assert top_factor(p_wind, p_flood) == factor


def test_risk_items_carry_the_band_and_the_top_factor(client: TestClient) -> None:
    advance_to(client, 3)
    config = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").risk.band_min_p_fail

    items = client.get("/risk", params={"advisory": 3}).json()["items"]
    explained = client.get(f"/assets/{items[0]['asset_id']}/explain", params={"advisory": 3}).json()

    assert all(i["risk_band"] == risk_band(i["p_fail"], config) for i in items)
    assert items[0]["top_factor"] == top_factor(explained["p_wind"], explained["p_flood"])
