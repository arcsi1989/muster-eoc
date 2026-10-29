"""Seam 2: the rule engine, one test per rule in playbook_rules.yaml, plus prohibition blocking
and deadline escalation. Seam 1: the section 8 rows that need only data and the engine."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.playbook.clauses import parse_clauses
from app.playbook.engine import Entity, Finding, evaluate, holds
from app.playbook.rules import Predicate, load_rulebook

SETTINGS = get_settings()
RULEBOOK = load_rulebook(SETTINGS.playbook_rules_path)

FALSE_STATE = {
    "inspection_completed": False,
    "generator_assigned": False,
    "barrier_installed": False,
    "backup_power_confirmed": False,
    "chem_stock_confirmed": False,
    "boil_water_notice_ready": False,
    "critical_customer_contacted": False,
}


def event(hours: int, **overrides: Any) -> dict[str, Any]:
    level = "prepare" if hours > 48 else "full"
    values = {
        "hours_to_landfall": hours,
        "activation_level": level,
        "hours_since_full_activation": 48 - hours if level == "full" else None,
        "regulator_notified": False,
        "generators_fuelled": 6,
        "wtp_pump_stations_top25": 8,
        "risk_list_reviewed_current": False,
        "sitrep_approved_current": False,
    }
    return {**values, **overrides}


def asset(
    asset_id: str = "A-1",
    asset_type: str = "substation",
    state: dict[str, bool] | None = None,
    **fields: Any,
) -> Entity:
    exposure = {
        k: fields.pop(k)
        for k in list(fields)
        if k in ("flood_depth_p90_m", "wind_p50_mph", "tsforce_arrival_h")
    }
    values = {
        "id": asset_id,
        "type": asset_type,
        "condition_score": 2,
        "distance_to_coast_km": 20.0,
        "feeds_facility_types": [],
        "feeds_facility_ids": [],
        "risk_rank": 100,
        "p_fail": 0.05,
        **fields,
    }
    return Entity(
        asset_id,
        "asset",
        {
            "asset": values,
            "exposure": {"flood_depth_p90_m": 0.0, **exposure},
            "state": {**FALSE_STATE, **(state or {})},
        },
    )


def staging(area_id: str, flood: float, relocated: bool = False) -> Entity:
    return Entity(
        area_id,
        "staging_area",
        {"staging": {"id": area_id, "flood_depth_p90_m": flood}, "state": {"relocated": relocated}},
    )


def findings(hours: int, entities: list[Entity], **event_overrides: Any) -> list[Finding]:
    return evaluate(RULEBOOK, event(hours, **event_overrides), entities)


def one(found: list[Finding], rule_id: str, entity_id: str = "event") -> Finding:
    matches = [f for f in found if f.rule_id == rule_id and f.entity_id == entity_id]
    assert len(matches) == 1, f"expected one {rule_id} finding for {entity_id}, got {matches}"
    return matches[0]


def absent(found: list[Finding], rule_id: str) -> bool:
    return not any(f.rule_id == rule_id for f in found)


def test_p_4_1_risk_list_review_is_open_until_recorded() -> None:
    assert one(findings(72, []), "P-4.1").status == "open"
    assert one(findings(72, [], risk_list_reviewed_current=True), "P-4.1").status == "satisfied"
    assert absent(findings(84, []), "P-4.1"), "inactive before T-72"


def test_p_4_2_coastal_pumping_station_at_flood_risk_needs_inspection() -> None:
    station = asset("PS-14", "pump_station", distance_to_coast_km=2.0, flood_depth_p90_m=0.8)
    inland = asset("PS-90", "pump_station", distance_to_coast_km=12.0, flood_depth_p90_m=0.8)
    dry = asset("PS-91", "pump_station", distance_to_coast_km=2.0, flood_depth_p90_m=0.4)

    found = findings(48, [station, inland, dry])

    assert one(found, "P-4.2", "PS-14").status == "open"
    assert [f.entity_id for f in found if f.rule_id == "P-4.2"] == ["PS-14"]
    inspected = asset(
        "PS-14",
        "pump_station",
        {"inspection_completed": True},
        distance_to_coast_km=2.0,
        flood_depth_p90_m=0.8,
    )
    assert one(findings(48, [inspected]), "P-4.2", "PS-14").status == "satisfied"
    assert absent(findings(60, [station]), "P-4.2"), "inactive before T-48"


def test_p_4_3_compares_fuelled_generators_with_pumping_stations_serving_the_plant() -> None:
    gap = one(findings(72, [], generators_fuelled=6, wtp_pump_stations_top25=8), "P-4.3")
    enough = one(findings(72, [], generators_fuelled=8, wtp_pump_stations_top25=8), "P-4.3")

    assert gap.status == "open"
    assert gap.details == {"event.generators_fuelled": 6, "event.wtp_pump_stations_top25": 8}
    assert enough.status == "satisfied"


def test_p_4_4_poor_condition_substation_in_the_top_10() -> None:
    poor = asset("SUB-3", condition_score=4, risk_rank=7)
    good = asset("SUB-4", condition_score=3, risk_rank=2)
    poor_low = asset("SUB-5", condition_score=5, risk_rank=11)

    found = findings(72, [poor, good, poor_low])

    assert [f.entity_id for f in found if f.rule_id == "P-4.4"] == ["SUB-3"]


def test_p_4_5_pumping_station_serving_the_plant_at_risk_needs_a_generator() -> None:
    ps9 = asset(
        "PS-09",
        "pump_station",
        feeds_facility_types=["treatment_plant"],
        feeds_facility_ids=["WTP-01"],
        p_fail=0.25,
    )
    low = asset("PS-10", "pump_station", feeds_facility_types=["treatment_plant"], p_fail=0.19)

    finding = one(findings(48, [ps9, low]), "P-4.5", "PS-09")

    assert finding.status == "open"
    assert finding.details["asset.feeds_facility_ids"] == ["WTP-01"]
    assert absent(findings(48, [low]), "P-4.5")


def test_p_4_5_never_matches_a_substation() -> None:
    feeds_plant = asset(
        "SUB-01",
        feeds_facility_types=["treatment_plant"],
        feeds_facility_ids=["WTP-01"],
        p_fail=0.9,
    )
    feeds_hospital = asset(
        "SUB-07", feeds_facility_types=["hospital"], feeds_facility_ids=["HOSP-01"], p_fail=0.9
    )
    hospital_only = asset("PS-20", "pump_station", feeds_facility_types=["hospital"], p_fail=0.9)

    assert absent(findings(48, [feeds_plant, feeds_hospital, hospital_only]), "P-4.5")


def test_p_4_6_flooding_staging_area_must_be_left() -> None:
    found = findings(36, [staging("STG-02", 0.2), staging("STG-01", 0.0)])

    assert one(found, "P-4.6", "STG-02").status == "open"
    assert absent([f for f in found if f.entity_id == "STG-01"], "P-4.6")
    assert (
        one(findings(36, [staging("STG-02", 0.2, relocated=True)]), "P-4.6", "STG-02").status
        == "satisfied"
    )
    assert absent(findings(48, [staging("STG-02", 0.2)]), "P-4.6"), "inactive before T-36"


def test_p_4_7_stop_work_turns_field_work_into_a_conflict() -> None:
    station = asset(
        "PS-14",
        "pump_station",
        distance_to_coast_km=2.0,
        flood_depth_p90_m=0.8,
        tsforce_arrival_h=8.0,
    )

    found = findings(24, [station])

    conflict = one(found, "P-4.2", "PS-14")
    assert conflict.status == "conflict"
    assert conflict.cites == ["P-4.2", "P-4.7", "P-8.2"]
    assert conflict.severity == "critical"
    assert conflict.owner_role == "incident_commander"
    assert absent(found, "P-4.7"), "a prohibition is never a finding on its own"


def test_p_4_7_does_not_block_work_without_field_work_or_far_from_the_wind() -> None:
    station = asset(
        "PS-14",
        "pump_station",
        distance_to_coast_km=2.0,
        flood_depth_p90_m=0.8,
        tsforce_arrival_h=8.0,
    )
    far = asset(
        "PS-15",
        "pump_station",
        distance_to_coast_km=2.0,
        flood_depth_p90_m=0.8,
        tsforce_arrival_h=20.0,
    )

    found = findings(24, [station, far])

    assert one(found, "P-5.2", "PS-14").status == "open", "backup power needs no field work"
    assert one(found, "P-4.2", "PS-15").status == "open"


def test_p_5_1_flood_barriers_at_substations() -> None:
    found = findings(
        36, [asset("SUB-11", flood_depth_p90_m=0.4), asset("SUB-12", flood_depth_p90_m=0.2)]
    )

    assert [f.entity_id for f in found if f.rule_id == "P-5.1"] == ["SUB-11"]


def test_p_5_2_backup_power_at_flood_exposed_pumping_stations() -> None:
    found = findings(48, [asset("PS-14", "pump_station", flood_depth_p90_m=0.6)])

    assert one(found, "P-5.2", "PS-14").status == "open"


def test_p_5_3_treatment_plant_needs_both_chemicals_and_notice() -> None:
    half = asset("WTP-01", "treatment_plant", {"chem_stock_confirmed": True}, p_fail=0.12)
    both = asset(
        "WTP-01",
        "treatment_plant",
        {"chem_stock_confirmed": True, "boil_water_notice_ready": True},
        p_fail=0.12,
    )

    assert one(findings(48, [half]), "P-5.3", "WTP-01").status == "open"
    assert one(findings(48, [both]), "P-5.3", "WTP-01").status == "satisfied"
    assert absent(findings(48, [asset("WTP-01", "treatment_plant", p_fail=0.05)]), "P-5.3")


def test_p_6_2_contact_hospitals_fed_by_top_25_assets() -> None:
    found = findings(
        48,
        [
            asset("SUB-07", feeds_facility_types=["hospital"], risk_rank=16),
            asset("SUB-09", feeds_facility_types=["hospital"], risk_rank=30),
        ],
    )

    assert [f.entity_id for f in found if f.rule_id == "P-6.2"] == ["SUB-07"]


def test_p_7_1_situation_report_approved_this_period() -> None:
    assert one(findings(72, []), "P-7.1").status == "open"
    assert one(findings(72, [], sitrep_approved_current=True), "P-7.1").status == "satisfied"


def test_p_7_2_regulator_deadline_escalates_after_12_hours_of_full_activation() -> None:
    at_deadline = one(findings(36, []), "P-7.2")
    overdue = one(findings(24, []), "P-7.2")
    notified = one(findings(24, [], regulator_notified=True), "P-7.2")

    assert (at_deadline.status, at_deadline.overdue, at_deadline.severity) == (
        "open",
        False,
        "high",
    )
    assert (overdue.status, overdue.overdue, overdue.severity) == ("open", True, "critical")
    assert (notified.status, notified.overdue) == ("satisfied", False)
    assert absent(findings(60, []), "P-7.2"), "only at full activation"


VALUES = {
    "asset": {"type": "substation", "rank": 7, "types": ["hospital"], "flag": False, "none": None}
}


@pytest.mark.parametrize(
    ("field", "op", "value", "expected"),
    [
        ("asset.type", "eq", "substation", True),
        ("asset.type", "ne", "substation", False),
        ("asset.rank", "gt", 7, False),
        ("asset.rank", "ge", 7, True),
        ("asset.rank", "lt", 8, True),
        ("asset.rank", "le", 6, False),
        ("asset.type", "in", ["substation", "pump_station"], True),
        ("asset.type", "in", None, False),
        ("asset.types", "contains_any", ["hospital", "shelter"], True),
        ("asset.types", "contains_any", ["shelter"], False),
        ("asset.type", "contains_any", ["sub"], False),
        ("asset.flag", "is_false", None, True),
        ("asset.flag", "is_true", None, False),
        ("asset.none", "is_false", None, False),
        ("asset.missing", "eq", "x", False),
    ],
)
def test_every_operator(field: str, op: str, value: Any, expected: bool) -> None:
    assert holds(Predicate(field=field, op=op, value=value), VALUES) is expected  # type: ignore[arg-type]


def test_value_field_compares_two_fields_and_fails_when_the_other_is_missing() -> None:
    values = {"event": {"fuelled": 6, "needed": 8}}

    assert holds(Predicate(field="event.fuelled", op="lt", value_field="event.needed"), values)
    assert not holds(Predicate(field="event.fuelled", op="lt", value_field="event.absent"), values)


def test_every_rule_in_the_yaml_has_a_test_here() -> None:
    source = open(__file__).read()

    for rule in RULEBOOK.rules:
        assert f"test_{rule.id.lower().replace('-', '_').replace('.', '_')}" in source, rule.id


def test_the_playbook_has_29_clauses() -> None:
    clauses = parse_clauses(SETTINGS.playbook_path)

    assert len(clauses) == 29
    p82 = next(c for c in clauses if c.id == "P-8.2")
    assert p82.title == "Conflicting clauses"
    assert p82.section == "8. Deviations and conflicts"
    assert "safety of personnel prevails" in p82.text


# Seam 1: section 8 rows that need only data and the engine (initial state, no decisions).


def findings_at(client: TestClient, advisory: int, **params: str) -> list[dict[str, Any]]:
    while client.get("/advisories").json()["current_advisory"] < advisory:
        assert client.post("/advisories/next").status_code == 200
    result: list[dict[str, Any]] = client.get(
        "/findings", params={"advisory": advisory, **params}
    ).json()
    return result


def find(found: list[dict[str, Any]], rule_id: str, entity_id: str = "event") -> dict[str, Any]:
    return next(f for f in found if f["rule_id"] == rule_id and f["entity_id"] == entity_id)


def test_advisory_1_prepare_with_review_generator_gap_and_sitrep_open(client: TestClient) -> None:
    found = findings_at(client, 1)

    assert {f["rule_id"] for f in found if f["status"] == "open"} >= {"P-4.1", "P-4.3", "P-7.1"}
    gap = find(found, "P-4.3")
    assert gap["status"] == "open"
    assert gap["details"]["event.generators_fuelled"] == 6
    assert gap["details"]["event.wtp_pump_stations_top25"] >= 8


def test_advisory_2_poor_condition_substation_in_top_10(client: TestClient) -> None:
    found = findings_at(client, 2)

    assert any(f["rule_id"] == "P-4.4" and f["status"] == "open" for f in found)


def test_advisory_3_full_activation_gaps(client: TestClient) -> None:
    found = findings_at(client, 3)

    ps9 = find(found, "P-4.5", "PS-09")
    assert ps9["status"] == "open"
    assert "WTP-01" in ps9["details"]["asset.feeds_facility_ids"]
    assert not any(f["rule_id"] == "P-4.5" and f["entity_id"].startswith("SUB-") for f in found), (
        "portable generators never go to substations"
    )
    assert find(found, "P-4.2", "PS-14")["status"] == "open"
    regulator = find(found, "P-7.2")
    assert (regulator["status"], regulator["overdue"]) == ("open", False)


def test_advisory_4_staging_area_barriers_and_regulator_not_yet_overdue(client: TestClient) -> None:
    found = findings_at(client, 4)

    assert find(found, "P-4.6", "STG-02")["status"] == "open"
    assert find(found, "P-4.6", "STG-02")["entity_name"] == "Harborfront Yard"
    assert any(f["rule_id"] == "P-5.1" and f["status"] == "open" for f in found)
    assert find(found, "P-7.2")["overdue"] is False


def test_advisory_5_ps_14_conflict_and_regulator_overdue(client: TestClient) -> None:
    found = findings_at(client, 5)

    conflict = find(found, "P-4.2", "PS-14")
    assert conflict["status"] == "conflict"
    assert conflict["cites"] == ["P-4.2", "P-4.7", "P-8.2"]
    assert find(found, "P-7.2")["overdue"] is True


def test_findings_filter_by_status_and_need_an_issued_advisory(client: TestClient) -> None:
    assert client.get("/findings", params={"advisory": 1}).status_code == 404

    conflicts = findings_at(client, 5, status="conflict")

    assert conflicts and all(f["status"] == "conflict" for f in conflicts)


def test_clauses_are_served(client: TestClient) -> None:
    clauses = client.get("/clauses").json()

    assert len(clauses) == 29
    assert clauses[0]["id"] == "P-1.1"


@pytest.mark.parametrize("flag", ["risk_list_reviewed_current", "sitrep_approved_current"])
def test_per_advisory_flags_start_false_at_each_advisory(client: TestClient, flag: str) -> None:
    found = findings_at(client, 2)

    rule = "P-4.1" if flag == "risk_list_reviewed_current" else "P-7.1"
    assert find(found, rule)["details"][f"event.{flag}"] is False
