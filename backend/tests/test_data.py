"""Seam 3: the gold data generator and the loader."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from muster.config import REPO_ROOT
from muster.datagen.generate import export_schemas, generate
from muster.db import create_fresh_engine
from muster.ingest.loader import GoldDataMissing, load_gold
from muster.models import QualityIssue

GOLD = REPO_ROOT / "data" / "gold"
FIRST_ADVISORY = date(2026, 9, 1)


def hashes(directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def gold(name: str) -> Any:
    return json.loads((GOLD / name).read_text())


def test_two_runs_give_identical_files(tmp_path: Path) -> None:
    generate(tmp_path / "a")
    generate(tmp_path / "b")

    assert hashes(tmp_path / "a") == hashes(tmp_path / "b")


def test_committed_gold_data_and_schemas_are_up_to_date(tmp_path: Path) -> None:
    generate(tmp_path / "gold")
    export_schemas(tmp_path / "contracts")

    assert hashes(tmp_path / "gold") == hashes(GOLD), "run `make data` and commit"
    assert hashes(tmp_path / "contracts") == hashes(REPO_ROOT / "contracts")


def test_asset_mix_follows_the_plan() -> None:
    types = [a["type"] for a in gold("assets.json")]

    assert types.count("substation") == 120
    assert types.count("pump_station") == 75
    assert types.count("treatment_plant") == 1


def test_sub_07_feeds_bayport_general_not_yet_contacted() -> None:
    deps = gold("dependencies.json")
    hospital = next(f for f in gold("critical_facilities.json") if f["id"] == "HOSP-01")
    sub07 = gold("initial_state.json")["entities"]["SUB-07"]

    assert {"from_id": "SUB-07", "to_id": "HOSP-01", "to_kind": "facility"} in deps
    assert hospital["name"] == "Bayport General Hospital"
    assert sub07["critical_customer_contacted"] is False
    assert sub07["hospital_backup_confirmed"] is False


def test_ps_14_is_a_coastal_pumping_station() -> None:
    ps14 = next(a for a in gold("assets.json") if a["id"] == "PS-14")

    assert ps14["type"] == "pump_station"
    assert ps14["distance_to_coast_km"] <= 5


def test_stg_02_is_the_only_coastal_staging_area() -> None:
    coastal = [s["id"] for s in gold("staging_areas.json") if s["distance_to_coast_km"] <= 5]

    assert coastal == ["STG-02"]


def test_six_generators_are_fuelled_at_the_start() -> None:
    assert gold("initial_state.json")["event"]["generators_fuelled"] == 6


def test_three_assets_have_no_elevation_and_five_have_stale_inspections() -> None:
    assets = gold("assets.json")
    stale = [
        a
        for a in assets
        if (FIRST_ADVISORY - date.fromisoformat(a["last_inspection_date"])).days > 3 * 365
    ]

    assert len([a for a in assets if a["elevation_m"] is None]) == 3
    assert len(stale) == 5


def test_every_dependency_points_at_a_known_entity() -> None:
    ids = {a["id"] for a in gold("assets.json")} | {
        f["id"] for f in gold("critical_facilities.json")
    }

    assert all(d["from_id"] in ids and d["to_id"] in ids for d in gold("dependencies.json"))


def test_loader_rejects_exactly_the_two_bad_example_rows(client: TestClient) -> None:
    lineage = {entry["file"]: entry for entry in client.get("/lineage").json()}

    example = lineage["assets_rejected_example.json"]
    assert example["rows_ok"] == 0
    assert example["rows_rejected"] == 2
    reasons = [issue["reason"] for issue in example["issues"]]
    assert reasons[0].startswith("customers_served")
    assert reasons[1].startswith("type")
    assert all(
        entry["rows_rejected"] == 0
        for name, entry in lineage.items()
        if name != "assets_rejected_example.json"
    )


def test_lineage_records_every_gold_file_with_its_hash(client: TestClient) -> None:
    lineage = {entry["file"]: entry for entry in client.get("/lineage").json()}

    assert set(lineage) == set(hashes(GOLD))
    assert lineage["assets.json"]["rows_ok"] == 196
    assert lineage["assets.json"]["sha256"] == hashes(GOLD)["assets.json"]


def test_rejected_rows_never_reach_the_api(client: TestClient) -> None:
    ids = {a["id"] for a in client.get("/assets").json()}

    assert len(ids) == 196
    assert not {"SUB-121", "SUB-122"} & ids


def test_duplicate_ids_and_dangling_dependencies_are_rejected(tmp_path: Path) -> None:
    generate(tmp_path)
    assets = json.loads((tmp_path / "assets.json").read_text())
    (tmp_path / "assets.json").write_text(json.dumps([*assets, assets[0]]))
    deps = json.loads((tmp_path / "dependencies.json").read_text())
    dangling = {"from_id": "SUB-999", "to_id": "PS-01", "to_kind": "asset"}
    (tmp_path / "dependencies.json").write_text(json.dumps([*deps, dangling]))

    with Session(create_fresh_engine(tmp_path / "db.sqlite")) as session:
        load_gold(session, tmp_path)
        reasons = {(i.file, i.row, i.reason) for i in session.exec(select(QualityIssue))}

    assert ("assets.json", len(assets), f"id: duplicate id {assets[0]['id']}") in reasons
    assert ("dependencies.json", len(deps), "from_id: unknown asset SUB-999") in reasons


def test_missing_gold_file_stops_the_load_with_a_hint(tmp_path: Path) -> None:
    generate(tmp_path)
    (tmp_path / "staging_areas.json").unlink()

    with (
        Session(create_fresh_engine(tmp_path / "db.sqlite")) as session,
        pytest.raises(GoldDataMissing, match="make data"),
    ):
        load_gold(session, tmp_path)


def test_facilities_and_staging_areas_are_served(client: TestClient) -> None:
    facilities = client.get("/facilities").json()
    staging = client.get("/staging-areas").json()

    assert len([f for f in facilities if f["type"] == "hospital"]) == 8
    assert len([f for f in facilities if f["type"] == "shelter"]) == 22
    assert [s["id"] for s in staging] == ["STG-01", "STG-02", "STG-03", "STG-04", "STG-05"]


# Real Florida places near the coast the scenario's storm is modelled on (plus the plan's own
# "Bayport", which it requires). None may appear in the fictional territory's names.
REAL_PLACES = [
    "Clearwater", "Palmetto", "Sawgrass", "Pine Ridge", "Naples", "Tampa", "Sarasota", "Fort Myers",
    "Cape Coral", "Punta Gorda", "Port Charlotte", "Sanibel", "Captiva", "Cayo Costa", "Venice",
    "Englewood", "Bradenton", "Pensacola", "Tallahassee", "Panama City", "Mexico Beach", "Destin",
    "Cedar Key", "Keaton Beach", "Marco Island", "Bonita", "Estero", "Largo", "Dunedin", "Miami",
    "Orlando", "Key West", "Florida",
]  # fmt: skip


def test_no_real_place_names_in_the_territory() -> None:
    names = [
        r["name"]
        for f in ("assets.json", "critical_facilities.json", "staging_areas.json")
        for r in gold(f)
    ]

    offending = [n for n in names for place in REAL_PLACES if place.lower() in n.lower()]
    assert offending == []


def test_every_asset_and_staging_area_has_a_district_and_bayport_east_holds_ps_14() -> None:
    assets = {a["id"]: a for a in gold("assets.json")}
    staging = gold("staging_areas.json")

    assert all(r["district"] for r in [*assets.values(), *staging])
    assert assets["PS-14"]["district"] == "Bayport East"
    assert len({a["district"] for a in assets.values()}) > 1
