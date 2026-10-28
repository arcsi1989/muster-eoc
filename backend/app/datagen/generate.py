"""Writes the gold files for the fictional territory.

Toy version for the walking skeleton: about 10 hand-placed assets and 5 advisories whose
forecast landfall shifts east between advisories 2 and 4 (docs/decisions.md). Deterministic:
two runs give identical files.

Run from backend/:  uv run python -m app.datagen.generate
"""

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT

TERRITORY_WIDTH_KM = 240
TERRITORY_DEPTH_KM = 200
HOURS_TO_LANDFALL = [72, 60, 48, 36, 24]
VMAX_MPH = [130, 130, 135, 140, 145]
PEAK_SURGE_M = [2.5, 2.5, 3.0, 3.5, 4.0]
LANDFALL_X_KM = [80.0, 80.0, 120.0, 160.0, 160.0]
RMAX_KM = 37.0
FORWARD_SPEED_KMH = 14.0
CONE_RADIUS_KM = {"12": 48, "24": 72, "36": 96, "48": 124, "60": 156, "72": 185, "96": 263}
FIRST_ISSUED_AT = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)

ASSETS: list[dict[str, Any]] = [
    {
        "id": "SUB-01",
        "name": "Harbor Road Substation",
        "type": "substation",
        "x_km": 70.0,
        "y_km": 62.0,
        "customers_served": 8200,
    },
    {
        "id": "SUB-02",
        "name": "Mill Creek Substation",
        "type": "substation",
        "x_km": 105.0,
        "y_km": 75.0,
        "customers_served": 6400,
    },
    {
        "id": "SUB-03",
        "name": "Pine Ridge Substation",
        "type": "substation",
        "x_km": 150.0,
        "y_km": 70.0,
        "customers_served": 9100,
    },
    {
        "id": "SUB-04",
        "name": "North Fork Substation",
        "type": "substation",
        "x_km": 120.0,
        "y_km": 140.0,
        "customers_served": 5300,
    },
    {
        "id": "SUB-05",
        "name": "Lakeside Substation",
        "type": "substation",
        "x_km": 200.0,
        "y_km": 110.0,
        "customers_served": 7000,
    },
    {
        "id": "SUB-07",
        "name": "Medical District Substation",
        "type": "substation",
        "x_km": 128.0,
        "y_km": 66.0,
        "customers_served": 4800,
    },
    {
        "id": "PS-03",
        "name": "Inlet Pumping Station",
        "type": "pump_station",
        "x_km": 45.0,
        "y_km": 66.0,
        "customers_served": 2100,
    },
    {
        "id": "PS-09",
        "name": "Upland Pumping Station",
        "type": "pump_station",
        "x_km": 90.0,
        "y_km": 120.0,
        "customers_served": 1800,
    },
    {
        "id": "PS-14",
        "name": "Seawall Pumping Station",
        "type": "pump_station",
        "x_km": 165.0,
        "y_km": 44.0,
        "customers_served": 2600,
    },
    {
        "id": "WTP-01",
        "name": "Bayport Water Treatment Plant",
        "type": "treatment_plant",
        "x_km": 140.0,
        "y_km": 105.0,
        "customers_served": 0,
    },
]


def coast_y_km(x_km: float) -> float:
    """The synthetic coastline: land lies north of it, open water south."""
    return 50.0 + 10.0 * math.sin(x_km / 35.0)


def coastline() -> dict[str, Any]:
    line = [[float(x), round(coast_y_km(x), 3)] for x in range(0, TERRITORY_WIDTH_KM + 1, 5)]
    land = [
        *line,
        [float(TERRITORY_WIDTH_KM), float(TERRITORY_DEPTH_KM)],
        [0.0, float(TERRITORY_DEPTH_KM)],
        line[0],
    ]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "coastline"},
                "geometry": {"type": "LineString", "coordinates": line},
            },
            {
                "type": "Feature",
                "properties": {"name": "land"},
                "geometry": {"type": "Polygon", "coordinates": [land]},
            },
        ],
    }


def advisory(index: int) -> dict[str, Any]:
    """A straight northward track to landfall after hours_to_landfall, 6-hourly to 24 h after."""
    hours = HOURS_TO_LANDFALL[index]
    landfall_x = LANDFALL_X_KM[index]
    landfall_y = coast_y_km(landfall_x)
    vmax = VMAX_MPH[index]
    track = []
    for t in range(0, hours + 25, 6):
        hours_after_landfall = t - hours
        decay = 1.0 if hours_after_landfall <= 0 else max(0.4, 1.0 - 0.025 * hours_after_landfall)
        track.append(
            {
                "t_hours": float(t),
                "x_km": landfall_x,
                "y_km": round(landfall_y + FORWARD_SPEED_KMH * hours_after_landfall, 3),
                "vmax_mph": round(vmax * decay, 1),
                "rmax_km": RMAX_KM,
            }
        )
    return {
        "advisory_no": index + 1,
        "issued_at": (FIRST_ISSUED_AT + timedelta(hours=12 * index)).isoformat(),
        "hours_to_landfall": hours,
        "track": track,
        "cone_radius_km": CONE_RADIUS_KM,
        "landfall": {"x_km": landfall_x, "y_km": round(landfall_y, 3)},
        "peak_surge_m": PEAK_SURGE_M[index],
    }


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def generate(out_dir: Path) -> None:
    write_json(out_dir / "assets.json", ASSETS)
    write_json(out_dir / "coastline.geojson", coastline())
    for index in range(len(HOURS_TO_LANDFALL)):
        write_json(out_dir / "advisories" / f"adv_{index + 1:02d}.json", advisory(index))


if __name__ == "__main__":
    generate(REPO_ROOT / "data" / "gold")
