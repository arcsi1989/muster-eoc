"""Writes the gold files for the fictional territory (docs/IMPLEMENTATION_PLAN.md section 2).

Seeded (42) and deterministic: two runs give byte-identical files. The demo seed assets are placed
by construction relative to the scripted storm (docs/decisions.md); everything else is random.
Storm values follow docs/research/florida-hurricanes.md (an unnamed storm modelled on a 2022 Gulf
landfall). No real place, utility, facility or person names.

Run from backend/:  uv run python -m muster.datagen.generate   (or `make data`)
"""

import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

from muster.config import REPO_ROOT
from muster.datagen.truth import HiddenTruth, simulate_failures
from muster.geo import distance_to_polyline
from muster.ingest.contracts import (
    AdvisoryRecord,
    AssetRecord,
    CoastlineFile,
    DependencyRecord,
    DistrictRecord,
    FacilityRecord,
    FragilityCurveRecord,
    HistoricalStormFile,
    InitialStateFile,
    StagingAreaRecord,
    StormOutcomeRecord,
    SyntheticStormFile,
)
from muster.models import FragilityCurve
from muster.playbook.activation import Level
from muster.scoring_config import load_scoring_config

SEED = 42
SCENARIO_START = date(2026, 9, 1)

# Territory: land lies north of the coastline, open water south of it.
TERRITORY_WIDTH_KM = 260
TERRITORY_DEPTH_KM = 220

# Storm (research note): five advisories, the forecast landfall shifts ~40 km east at 3 and at 4.
HOURS_TO_LANDFALL = [72, 60, 48, 36, 24]
VMAX_MPH = [130, 130, 135, 140, 145]
PEAK_SURGE_M = [2.5, 2.5, 3.0, 3.5, 4.0]
LANDFALL_X_KM = [80.0, 80.0, 120.0, 160.0, 160.0]
RMAX_KM = 37.0
FORWARD_SPEED_KMH = 14.0
HEADING_DEG_FROM_EAST = 75.0  # moving north-north-east
CONE_RADIUS_KM = {"12": 48, "24": 72, "36": 96, "48": 124, "60": 156, "72": 185, "96": 263}
FIRST_ISSUED_AT = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)

N_SUBSTATIONS = 120
N_PUMP_STATIONS = 75
N_HOSPITALS = 8
N_SHELTERS = 22
FUELLED_GENERATORS = 6
INITIAL_ACTIVATION_LEVEL: Level = "monitor"  # declared at the start of the scenario (plan 2.3)

# Population centres: assets cluster around them (x_km, km inland, spread_km).
TOWNS = [(125, 8, 14), (60, 10, 12), (195, 8, 12), (100, 70, 15), (200, 95, 15), (45, 140, 15)]

STATE_KEYS_ASSET = [
    "inspection_completed",
    "generator_assigned",
    "barrier_installed",
    "backup_power_confirmed",
    "chem_stock_confirmed",
    "boil_water_notice_ready",
    "critical_customer_contacted",
    "hospital_backup_confirmed",
]
STATE_KEYS_STAGING = ["relocated"]

PLACE_WORDS = [
    "Harbor",
    "Mill Creek",
    "Pinewold Ridge",
    "Oak Hollow",
    "Cedar Point",
    "Sandy Flats",
    "Gull Bay",
    "Marsh End",
    "Heron Lake",
    "Fox Run",
    "Willow Bend",
    "Stone Gate",
    "Elm Park",
    "Saltmeadow",
    "Driftwood",
    "Lantern Hill",
    "Kingfisher",
    "Coral Lane",
    "Bluewater",
    "Mangrove",
    "Gullmere",
    "Tarrowfield",
    "Tidewater",
    "Orchard",
    "Brookside",
    "Juniper",
    "Magnolia",
    "Seabreeze",
    "Riverside",
    "Highfield",
    "Copperleaf",
    "Westmoor",
    "Eastgate",
    "Northwood",
    "Southpoint",
    "Lakeview",
    "Briar Patch",
    "Brinemoor Run",
    "Shell Beach",
    "Dune Crest",
]
SUFFIXES = ["", " North", " South", " East", " West"]


def coast_y_km(x_km: float) -> float:
    """The synthetic coastline, a gently curved line."""
    return 50.0 + 10.0 * math.sin(x_km / 35.0)


def coastline_points() -> list[tuple[float, float]]:
    return [(float(x), round(coast_y_km(x), 3)) for x in range(0, TERRITORY_WIDTH_KM + 1, 5)]


COAST = coastline_points()


# Fictional districts, west to east: each covers the territory from its western edge (x_km) to
# the next district's. PS-14 and STG-02 are in Bayport East; the city centre in Bayport West.
DISTRICTS = [
    ("Westshore", 0.0),
    ("Bayport West", 75.0),
    ("Bayport East", 135.0),
    ("Eastern Plains", 190.0),
]


# Where the maps write the districts' names (y_km): in the sparser band above the coastal towns,
# inside both maps' views.
DISTRICT_LABEL_Y_KM = 165.0


def district_for(x_km: float) -> str:
    return next(name for name, west in reversed(DISTRICTS) if x_km >= west)


def build_districts() -> list[dict[str, Any]]:
    """Each district's span from its western edge to the next one's (the last to the territory's
    eastern edge), and where its name sits on the maps."""
    edges = [west for _, west in DISTRICTS[1:]] + [float(TERRITORY_WIDTH_KM)]
    districts = []
    for (name, west), east in zip(DISTRICTS, edges, strict=True):
        districts.append(
            {
                "name": name,
                "west_km": west,
                "east_km": east,
                "label": {"x_km": (west + east) / 2, "y_km": DISTRICT_LABEL_Y_KM},
            }
        )
    return districts


def place_names(rng: random.Random, count: int, kind: str) -> list[str]:
    names = [f"{w}{s} {kind}" for s in SUFFIXES for w in PLACE_WORDS]
    rng.shuffle(names)
    return names[:count]


def inland_point(x_km: float, inland_km: float) -> tuple[float, float]:
    """A point inland_km north of the coast at x_km (clamped to the territory)."""
    x = min(TERRITORY_WIDTH_KM - 2.0, max(2.0, x_km))
    y = min(TERRITORY_DEPTH_KM - 2.0, coast_y_km(x) + max(0.5, inland_km))
    return round(x, 2), round(y, 2)


def random_site(rng: random.Random) -> tuple[float, float]:
    if rng.random() < 0.6:
        tx, inland, spread = rng.choice(TOWNS)
        return inland_point(rng.gauss(tx, spread), abs(rng.gauss(inland, spread / 2)))
    return inland_point(rng.uniform(5, TERRITORY_WIDTH_KM - 5), rng.uniform(1, 160))


def distance_to_coast(x: float, y: float) -> float:
    return round(distance_to_polyline(x, y, COAST), 2)


def elevation_for(rng: random.Random, distance_km: float) -> float:
    return round(max(0.3, 0.6 + 0.12 * distance_km + rng.gauss(0, 0.4)), 1)


def condition_for(rng: random.Random, install_year: int) -> int:
    age = SCENARIO_START.year - install_year
    return min(5, max(1, round(1 + age / 15 + rng.gauss(0, 0.8))))


def recent_inspection(rng: random.Random) -> date:
    return SCENARIO_START - timedelta(days=rng.randint(30, 700))


# Demo seeds (plan section 2.2), placed by construction. Values: (x_km, km inland, elevation,
# condition, install_year). The hazard-dependent facts are checked by seed_check.py.
ASSET_SEEDS: dict[str, tuple[float, float, float, int, int]] = {
    # Feeds HOSP-01 (Bayport General), near the converged landfall.
    "SUB-07": (126.0, 6.0, 2.4, 5, 1972),
    # Poor condition near the early landfall: P-4.4 in the top 10 at advisory 2.
    "SUB-03": (84.0, 4.0, 1.6, 4, 1971),
    # Low-lying substation near the late landfall: P-5.1 from advisory 4.
    "SUB-11": (158.0, 1.5, 0.8, 3, 1995),
    # Coastal pumping station: P-4.2 from advisory 3, stop-work (P-4.7) at advisory 5.
    "PS-14": (140.0, 2.0, 0.6, 3, 1984),
    # The one treatment plant, inland of the city.
    "WTP-01": (110.0, 25.0, 8.0, 2, 1979),
}
SEED_NAMES = {"SUB-07": "Medical District Substation", "PS-14": "Seawall Pumping Station"}
HOSPITAL_SEEDS = {"HOSP-01": ("Bayport General Hospital", 128.0, 9.0)}
STAGING_SEEDS = {
    "STG-01": ("Northfield Depot", 60.0, 70.0, None),
    "STG-02": ("Harborfront Yard", 168.0, 1.0, 2.3),  # the only coastal one; floods from advisory 4
    "STG-03": ("Ridgeline Depot", 130.0, 100.0, None),
    "STG-04": ("Eastern Plains Depot", 205.0, 80.0, None),
    "STG-05": ("Upland Fairground", 90.0, 130.0, None),
}
# The pumping stations that serve the treatment plant, between the early landfall and the city,
# just over 5 km inland (P-4.2 stays with PS-14). Values: (x_km, km inland, elevation, condition).
# At least 8 sit in the top 25 at advisory 1 (P-4.3 gap with 6 fuelled generators); PS-09, near
# the converged landfall, is the P-4.5 gap at advisory 3.
WTP_PUMP_SEEDS: dict[str, tuple[float, float, float, int]] = {
    "PS-09": (118.0, 6.0, 0.9, 5),
    "PS-19": (72.0, 6.0, 0.9, 5),
    "PS-42": (78.0, 6.0, 0.9, 5),
    "PS-48": (84.0, 6.0, 0.9, 5),
    "PS-53": (88.0, 6.0, 0.9, 5),
    "PS-54": (92.0, 6.0, 0.9, 5),
    "PS-60": (96.0, 6.0, 0.9, 5),
    "PS-40": (100.0, 6.0, 0.9, 5),
    "PS-21": (104.0, 6.0, 0.9, 5),
    "PS-34": (110.0, 6.0, 0.9, 5),
}
STALE_INSPECTIONS = ["SUB-22", "SUB-58", "SUB-91", "PS-33", "PS-61"]  # over 3 years old
NULL_ELEVATIONS = ["SUB-15", "SUB-44", "PS-27"]


def build_assets(rng: random.Random) -> list[dict[str, Any]]:
    ids = (
        [f"SUB-{i:02d}" for i in range(1, N_SUBSTATIONS + 1)]
        + [f"PS-{i:02d}" for i in range(1, N_PUMP_STATIONS + 1)]
        + ["WTP-01"]
    )
    sub_names = place_names(rng, N_SUBSTATIONS, "Substation")
    ps_names = place_names(rng, N_PUMP_STATIONS, "Pumping Station")
    assets = []
    for asset_id in ids:
        kind, number = asset_id.split("-")
        if asset_id in ASSET_SEEDS:
            sx, inland, elevation, condition, install_year = ASSET_SEEDS[asset_id]
            x, y = inland_point(sx, inland)
        else:
            x, y = random_site(rng)
            install_year = rng.randint(1965, 2020)
            condition = condition_for(rng, install_year)
            elevation = elevation_for(rng, distance_to_coast(x, y))
        if asset_id in WTP_PUMP_SEEDS:
            # Placed after the random draws, so every other asset keeps its random values.
            seed_x_km, inland, elevation, condition = WTP_PUMP_SEEDS[asset_id]
            x, y = inland_point(seed_x_km, inland)
        if kind == "SUB":
            asset_type, name = "substation", sub_names[int(number) - 1]
            customers = rng.randint(1500, 12000)
        elif kind == "PS":
            asset_type, name = "pump_station", ps_names[int(number) - 1]
            customers = rng.randint(300, 3000)
        else:
            asset_type, name, customers = "treatment_plant", "Bayport Water Treatment Plant", 85000
        name = SEED_NAMES.get(asset_id, name)
        inspected = (
            SCENARIO_START - timedelta(days=rng.randint(1150, 1500))
            if asset_id in STALE_INSPECTIONS
            else recent_inspection(rng)
        )
        assets.append(
            {
                "id": asset_id,
                "name": name,
                "type": asset_type,
                "x_km": x,
                "y_km": y,
                "elevation_m": None if asset_id in NULL_ELEVATIONS else elevation,
                "distance_to_coast_km": distance_to_coast(x, y),
                "install_year": install_year,
                "condition_score": condition,
                "last_inspection_date": inspected.isoformat(),
                "customers_served": customers,
                "district": district_for(x),
            }
        )
    return assets


def build_facilities(rng: random.Random) -> list[dict[str, Any]]:
    hospital_names = place_names(rng, N_HOSPITALS, "Hospital")
    shelter_names = place_names(rng, N_SHELTERS, "Shelter")
    facilities = []
    for i in range(1, N_HOSPITALS + 1):
        fid = f"HOSP-{i:02d}"
        if fid in HOSPITAL_SEEDS:
            name, sx, inland = HOSPITAL_SEEDS[fid]
            x, y = inland_point(sx, inland)
        else:
            name, (x, y) = hospital_names[i - 1], random_site(rng)
        facilities.append({"id": fid, "name": name, "type": "hospital", "x_km": x, "y_km": y})
    for i in range(1, N_SHELTERS + 1):
        x, y = inland_point(rng.uniform(10, TERRITORY_WIDTH_KM - 10), rng.uniform(15, 150))
        facilities.append(
            {
                "id": f"SHEL-{i:02d}",
                "name": shelter_names[i - 1],
                "type": "shelter",
                "x_km": x,
                "y_km": y,
            }
        )
    return facilities


def build_staging_areas(rng: random.Random) -> list[dict[str, Any]]:
    areas = []
    for sid, (name, sx, inland, elevation) in STAGING_SEEDS.items():
        x, y = inland_point(sx, inland)
        d = distance_to_coast(x, y)
        areas.append(
            {
                "id": sid,
                "name": name,
                "x_km": x,
                "y_km": y,
                "elevation_m": elevation if elevation is not None else elevation_for(rng, d),
                "distance_to_coast_km": d,
                "district": district_for(x),
            }
        )
    return areas


def _nearest(
    target: dict[str, Any], candidates: list[dict[str, Any]], count: int = 1
) -> list[dict[str, Any]]:
    def dist(c: dict[str, Any]) -> float:
        return math.hypot(c["x_km"] - target["x_km"], c["y_km"] - target["y_km"])

    return sorted(candidates, key=lambda c: (dist(c), c["id"]))[:count]


def build_dependencies(
    assets: list[dict[str, Any]], facilities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Substations feed pumping stations, the treatment plant and facilities; pumping stations
    feed the treatment plant (plan section 2.1). Nearest substation wins, except the seeds; the
    seeded pumping stations are the ones that serve the plant."""
    substations = [a for a in assets if a["type"] == "substation"]
    pump_stations = [a for a in assets if a["type"] == "pump_station"]
    plant = next(a for a in assets if a["type"] == "treatment_plant")
    others = [s for s in substations if s["id"] != "SUB-07"]  # SUB-07 feeds HOSP-01 only

    deps = []
    for ps in pump_stations:
        feeder = _nearest(ps, others)[0]
        deps.append({"from_id": feeder["id"], "to_id": ps["id"], "to_kind": "asset"})
    for feeder in _nearest(plant, others, 2):
        deps.append({"from_id": feeder["id"], "to_id": plant["id"], "to_kind": "asset"})
    for ps in (p for p in pump_stations if p["id"] in WTP_PUMP_SEEDS):
        deps.append({"from_id": ps["id"], "to_id": plant["id"], "to_kind": "asset"})
    for facility in facilities:
        feeder_id = "SUB-07" if facility["id"] == "HOSP-01" else _nearest(facility, others)[0]["id"]
        deps.append({"from_id": feeder_id, "to_id": facility["id"], "to_kind": "facility"})
    return sorted(deps, key=lambda d: (d["from_id"], d["to_id"]))


FRAGILITY_CURVES: list[dict[str, Any]] = [
    {"asset_type": "substation", "hazard": "wind", "theta": 140.0, "beta": 0.25},
    {"asset_type": "substation", "hazard": "flood", "theta": 0.8, "beta": 0.5},
    {"asset_type": "pump_station", "hazard": "wind", "theta": 150.0, "beta": 0.25},
    {"asset_type": "pump_station", "hazard": "flood", "theta": 1.0, "beta": 0.45},
    {"asset_type": "treatment_plant", "hazard": "wind", "theta": 160.0, "beta": 0.2},
    {"asset_type": "treatment_plant", "hazard": "flood", "theta": 1.5, "beta": 0.4},
]

# The hidden true curves (never written to gold) that Storm Delta's failures are drawn from. The
# published curves overstate every median capacity by 20 % (plan M8: the prior is about 20 % off).
TRUE_FRAGILITY_CURVES: list[dict[str, Any]] = [
    {**c, "theta": round(c["theta"] / 1.2, 3)} for c in FRAGILITY_CURVES
]
TRUE_CURVES = [FragilityCurve(**c) for c in TRUE_FRAGILITY_CURVES]

# Storm Delta, a past fictional storm: a straight best track through the eastern half of the
# territory, 6-hourly from 36 h before landfall to 24 h after.
DELTA_NAME = "Storm Delta"
DELTA_LANDFALL_AT = datetime(2021, 8, 29, 18, 0, tzinfo=UTC)
DELTA_LANDFALL_X_KM = 185.0
DELTA_HOURS_BEFORE_LANDFALL = 36
DELTA_VMAX_MPH = 130.0
DELTA_PEAK_SURGE_M = 3.0
DELTA_HEADING_DEG_FROM_EAST = 80.0


def build_initial_state(
    assets: list[dict[str, Any]], staging: list[dict[str, Any]]
) -> dict[str, Any]:
    entities = {a["id"]: dict.fromkeys(STATE_KEYS_ASSET, False) for a in assets}
    entities.update({s["id"]: dict.fromkeys(STATE_KEYS_STAGING, False) for s in staging})
    return {
        "entities": entities,
        "event": {
            "generators_fuelled": FUELLED_GENERATORS,
            "regulator_notified": False,
            "activation_level": INITIAL_ACTIVATION_LEVEL,
        },
    }


def build_coastline() -> dict[str, Any]:
    line = [list(p) for p in COAST]
    land = [*line, [TERRITORY_WIDTH_KM, TERRITORY_DEPTH_KM], [0.0, TERRITORY_DEPTH_KM], line[0]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "coastline", "crs": "planar_km"},
                "geometry": {"type": "LineString", "coordinates": line},
            },
            {
                "type": "Feature",
                "properties": {"name": "land", "crs": "planar_km"},
                "geometry": {"type": "Polygon", "coordinates": [land]},
            },
        ],
    }


def build_advisory(index: int) -> dict[str, Any]:
    """A straight track at constant forward speed through the forecast landfall point, 6-hourly
    from issue time to 24 h after landfall. Weakening over land is the hazard model's job."""
    hours = HOURS_TO_LANDFALL[index]
    track, landfall = straight_track(
        LANDFALL_X_KM[index], HEADING_DEG_FROM_EAST, float(VMAX_MPH[index]), RMAX_KM, hours
    )
    return {
        "advisory_no": index + 1,
        "issued_at": (FIRST_ISSUED_AT + timedelta(hours=12 * index)).isoformat(),
        "hours_to_landfall": hours,
        "track": track,
        "cone_radius_km": CONE_RADIUS_KM,
        "landfall": landfall,
        "peak_surge_m": PEAK_SURGE_M[index],
    }


def straight_track(
    landfall_x_km: float,
    heading_deg_from_east: float,
    vmax_mph: float,
    rmax_km: float,
    hours_before_landfall: int,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """A straight track at constant forward speed (an advisory's forecast or a past storm's best
    track), 6-hourly from `hours_before_landfall` before landfall to 24 h after, and its
    landfall point on the coast."""
    lx, ly = landfall_x_km, coast_y_km(landfall_x_km)
    heading = math.radians(heading_deg_from_east)
    track = []
    for t in range(0, hours_before_landfall + 25, 6):
        travelled = FORWARD_SPEED_KMH * (t - hours_before_landfall)
        track.append(
            {
                "t_hours": float(t),
                "x_km": round(lx + travelled * math.cos(heading), 3),
                "y_km": round(ly + travelled * math.sin(heading), 3),
                "vmax_mph": vmax_mph,
                "rmax_km": rmax_km,
            }
        )
    return track, {"x_km": lx, "y_km": round(ly, 3)}


def build_storm_delta() -> dict[str, Any]:
    track, landfall = straight_track(
        DELTA_LANDFALL_X_KM,
        DELTA_HEADING_DEG_FROM_EAST,
        DELTA_VMAX_MPH,
        RMAX_KM,
        DELTA_HOURS_BEFORE_LANDFALL,
    )
    return {
        "name": DELTA_NAME,
        "landfall_at": DELTA_LANDFALL_AT.isoformat(),
        "landfall_t_hours": float(DELTA_HOURS_BEFORE_LANDFALL),
        "track": track,
        "landfall": landfall,
        "peak_surge_m": DELTA_PEAK_SURGE_M,
    }


def build_storm_delta_outcomes(
    storm: dict[str, Any], assets: list[dict[str, Any]], coastline: dict[str, Any]
) -> list[dict[str, Any]]:
    """Which assets failed in Storm Delta: drawn (seeded) from the hidden true curves, applied to
    the exposure the back-test computes from the best track. Without the synthetic history's age
    x condition effect: the calibration and the demo seeds rest on these failures."""
    return simulate_failures(
        storm,
        assets,
        coastline,
        HiddenTruth(TRUE_CURVES, effect=None, year=SCENARIO_START.year),
        load_scoring_config(REPO_ROOT / "config" / "scoring.yaml"),
        np.random.default_rng(SEED),
    )


REJECTED_EXAMPLE = [
    {
        "id": "SUB-121",
        "name": "Saltmeadow Spur Substation",
        "type": "substation",
        "x_km": 101.0,
        "y_km": 80.0,
        "elevation_m": 4.1,
        "distance_to_coast_km": 30.2,
        "install_year": 1990,
        "condition_score": 2,
        "last_inspection_date": "2025-11-02",
        "customers_served": -350,  # negative customers
        "district": "Bayport West",
    },
    {
        "id": "SUB-122",
        "name": "Heron Lake Array",
        "type": "solar_farm",  # unknown asset type
        "x_km": 150.0,
        "y_km": 120.0,
        "elevation_m": 11.0,
        "distance_to_coast_km": 75.5,
        "install_year": 2019,
        "condition_score": 1,
        "last_inspection_date": "2026-03-14",
        "customers_served": 0,
        "district": "Bayport East",
    },
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def generate(out_dir: Path) -> None:
    rng = random.Random(SEED)
    assets = build_assets(rng)
    facilities = build_facilities(rng)
    staging = build_staging_areas(rng)
    write_json(out_dir / "assets.json", assets)
    write_json(out_dir / "assets_rejected_example.json", REJECTED_EXAMPLE)
    write_json(out_dir / "critical_facilities.json", facilities)
    write_json(out_dir / "districts.json", build_districts())
    write_json(out_dir / "staging_areas.json", staging)
    write_json(out_dir / "dependencies.json", build_dependencies(assets, facilities))
    write_json(out_dir / "fragility_curves.json", FRAGILITY_CURVES)
    write_json(out_dir / "initial_state.json", build_initial_state(assets, staging))
    coastline = build_coastline()
    write_json(out_dir / "coastline.geojson", coastline)
    delta = build_storm_delta()
    write_json(out_dir / "history" / "storm_delta_track.json", delta)
    write_json(
        out_dir / "history" / "storm_delta_outcomes.json",
        build_storm_delta_outcomes(delta, assets, coastline),
    )
    for index in range(len(HOURS_TO_LANDFALL)):
        write_json(out_dir / "advisories" / f"adv_{index + 1:02d}.json", build_advisory(index))


def export_schemas(out_dir: Path) -> None:
    """JSON Schemas for the gold files, exported from the Pydantic contracts."""
    contracts: dict[str, type[BaseModel]] = {
        "asset": AssetRecord,
        "dependency": DependencyRecord,
        "critical_facility": FacilityRecord,
        "district": DistrictRecord,
        "staging_area": StagingAreaRecord,
        "fragility_curve": FragilityCurveRecord,
        "initial_state": InitialStateFile,
        "advisory": AdvisoryRecord,
        "coastline": CoastlineFile,
        "historical_storm": HistoricalStormFile,
        "storm_outcome": StormOutcomeRecord,
        "synthetic_storm": SyntheticStormFile,
    }
    for name, model in contracts.items():
        write_json(out_dir / f"{name}.schema.json", model.model_json_schema())


if __name__ == "__main__":
    import sys

    from muster.config import get_settings
    from muster.datagen.seed_check import check_seeds

    generate(REPO_ROOT / "data" / "gold")
    export_schemas(REPO_ROOT / "contracts")
    settings = get_settings()
    failures = check_seeds(
        REPO_ROOT / "data" / "gold",
        load_scoring_config(settings.scoring_config_path),
    )
    if failures:
        print("Demo seed facts that do not hold:", *failures, sep="\n  - ", file=sys.stderr)
        sys.exit(1)
    print("Gold data written; all demo seed facts hold.")
