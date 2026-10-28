"""Forecast track helpers: hourly interpolation and the forecast cone."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.geo import FloatArray, Point, heading_unit_vector


@dataclass(frozen=True)
class HourlyTrack:
    t_hours: FloatArray
    xy: FloatArray  # N x 2
    vmax_mph: FloatArray
    rmax_km: FloatArray


def interpolate(track: list[dict[str, Any]], step_hours: float) -> HourlyTrack:
    t = np.array([p["t_hours"] for p in track], dtype=float)
    hours = np.arange(t[0], t[-1] + 1e-9, step_hours)

    def interp(key: str) -> FloatArray:
        values: FloatArray = np.interp(hours, t, [p[key] for p in track])
        return values

    return HourlyTrack(
        t_hours=hours,
        xy=np.column_stack([interp("x_km"), interp("y_km")]),
        vmax_mph=interp("vmax_mph"),
        rmax_km=interp("rmax_km"),
    )


def heading(track: list[dict[str, Any]]) -> Point:
    return heading_unit_vector(
        (track[0]["x_km"], track[0]["y_km"]), (track[-1]["x_km"], track[-1]["y_km"])
    )


def cone_radius(lead_hours: float, radii: dict[str, float]) -> float:
    """Cone radius at a lead time, interpolated between the published lead times."""
    leads = sorted((float(k), v) for k, v in radii.items())
    return float(np.interp(lead_hours, [k for k, _ in leads], [v for _, v in leads]))


def cone_polygon(track: list[dict[str, Any]], radii: dict[str, float]) -> list[Point]:
    """Outline of the forecast cone: the track widened sideways by the cone radius at each lead
    time (zero at issue time)."""
    hx, hy = heading(track)
    nx, ny = -hy, hx
    left, right = [], []
    for p in track:
        radius = cone_radius(p["t_hours"], {"0": 0.0, **radii})
        left.append((p["x_km"] + nx * radius, p["y_km"] + ny * radius))
        right.append((p["x_km"] - nx * radius, p["y_km"] - ny * radius))
    return [*left, *reversed(right)]
