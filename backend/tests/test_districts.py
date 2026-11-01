"""The districts (CR-02, ticket 36): drawn on both maps from the gold data pack, the one source
of the field view's district list too."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from muster.config import REPO_ROOT
from muster.datagen.generate import generate
from muster.db import create_fresh_engine
from muster.geo import inside_polygon
from muster.ingest.loader import GoldDataMissing, load_gold
from muster.models import QualityIssue

GOLD = REPO_ROOT / "data" / "gold"
WEST_TO_EAST = ["Westshore", "Bayport West", "Bayport East", "Eastern Plains"]


def test_the_districts_are_served_west_to_east_and_tile_the_territory(
    client: TestClient,
) -> None:
    districts = client.get("/districts").json()

    assert [d["name"] for d in districts] == WEST_TO_EAST
    assert districts[0]["west_km"] == 0
    assert all(a["east_km"] == b["west_km"] for a, b in zip(districts, districts[1:], strict=False))


def test_every_site_lies_in_the_district_it_names(client: TestClient) -> None:
    districts = {d["name"]: d for d in client.get("/districts").json()}
    sites = [
        *json.loads((GOLD / "assets.json").read_text()),
        *json.loads((GOLD / "staging_areas.json").read_text()),
    ]

    outside = [
        s["id"]
        for s in sites
        if not districts[s["district"]]["west_km"]
        <= s["x_km"]
        < districts[s["district"]]["east_km"]
    ]
    assert outside == []


def test_a_boundary_runs_inland_from_the_coast_between_each_pair_of_neighbours(
    client: TestClient,
) -> None:
    districts = client.get("/districts").json()
    coast = {p["x_km"]: p["y_km"] for p in client.get("/coastline").json()["coastline"]}

    assert districts[0]["boundary"] == [], "the westernmost district has no western neighbour"
    for district in districts[1:]:
        start, end = district["boundary"]
        assert start["x_km"] == end["x_km"] == district["west_km"]
        assert start["y_km"] == coast[district["west_km"]]
        assert end["y_km"] > start["y_km"]


def test_each_label_sits_on_land_inside_its_district(client: TestClient) -> None:
    land = [(p["x_km"], p["y_km"]) for p in client.get("/coastline").json()["land"]]

    for district in client.get("/districts").json():
        label = district["label"]
        assert district["west_km"] < label["x_km"] < district["east_km"]
        assert inside_polygon(np.array([[label["x_km"], label["y_km"]]]), land)[0]


def test_the_field_view_lists_the_served_districts(client: TestClient) -> None:
    names = [d["name"] for d in client.get("/districts").json()]

    assert client.get("/field/districts").json() == sorted(names)


def load_issues(gold_dir: Path) -> set[tuple[str, str]]:
    with Session(create_fresh_engine(gold_dir / "db.sqlite")) as session:
        load_gold(session, gold_dir)
        return {(i.file, i.reason) for i in session.exec(select(QualityIssue))}


def test_districts_that_overlap_or_leave_a_gap_stop_the_load(tmp_path: Path) -> None:
    generate(tmp_path)
    path = tmp_path / "districts.json"
    districts = json.loads(path.read_text())
    districts[2]["west_km"] -= 5  # overlaps Bayport West
    path.write_text(json.dumps(districts))

    with pytest.raises(GoldDataMissing, match="Bayport East starts at 130.0 km"):
        load_issues(tmp_path)


def test_a_site_in_an_unknown_district_is_rejected(tmp_path: Path) -> None:
    generate(tmp_path)
    path = tmp_path / "assets.json"
    assets = json.loads(path.read_text())
    assets[0]["district"] = "Nowhere"
    path.write_text(json.dumps(assets))

    issues = load_issues(tmp_path)

    assert ("assets.json", "district: unknown district Nowhere") in issues
