"""Forecast track helpers: hourly interpolation, the forecast cone and intensity categories."""

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
import shapely

from muster.geo import FloatArray, Point, heading_unit_vector
from muster.scoring_config import IntensityCategory


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
    """Cone radius at a lead time, interpolated between the published lead times (zero at issue
    time). The one source for both the drawn cone and the ensemble's sideways spread."""
    leads = sorted((float(k), v) for k, v in {"0": 0.0, **radii}.items())
    return float(np.interp(lead_hours, [k for k, _ in leads], [v for _, v in leads]))


@dataclass(frozen=True)
class Circle:
    x_km: float
    y_km: float
    radius_km: float


def cone_circles(track: list[dict[str, Any]], radii: dict[str, float]) -> list[Circle]:
    """One circle per forecast point, with the cone radius at that point's lead time."""
    return [Circle(p["x_km"], p["y_km"], cone_radius(p["t_hours"], radii)) for p in track]


def cone_polygon(track: list[dict[str, Any]], radii: dict[str, float]) -> list[Point]:
    """Outline of the forecast cone as NHC draws it: the convex hull of each pair of consecutive
    circles, all unioned."""
    shapes = [
        shapely.Point(c.x_km, c.y_km).buffer(c.radius_km)
        if c.radius_km > 0
        else shapely.Point(c.x_km, c.y_km)
        for c in cone_circles(track, radii)
    ]
    cone = shapely.union_all([shapely.union(a, b).convex_hull for a, b in pairwise(shapes)])
    if not isinstance(cone, shapely.Polygon):  # consecutive hulls share a circle: one shape
        raise ValueError("the forecast cone is not a single polygon")
    return [(round(x, 3), round(y, 3)) for x, y in cone.exterior.coords]


def intensity_category(
    vmax_mph: float, category_min_mph: dict[IntensityCategory, float]
) -> IntensityCategory:
    """The highest intensity category whose lowest wind `vmax_mph` reaches (Saffir-Simpson,
    thresholds from config)."""
    reached = [(mph, name) for name, mph in category_min_mph.items() if vmax_mph >= mph]
    return max(reached)[1]
