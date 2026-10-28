"""Geometry on the planar km grid of the fictional territory."""

import math
from collections.abc import Sequence

Point = tuple[float, float]


def distance_to_polyline(x_km: float, y_km: float, polyline: Sequence[Point]) -> float:
    """Shortest distance from a point to a polyline, in km."""
    best = math.inf
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:], strict=False):
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        t = (
            0.0
            if length_sq == 0
            else max(0.0, min(1.0, ((x_km - ax) * dx + (y_km - ay) * dy) / length_sq))
        )
        best = min(best, math.hypot(x_km - (ax + t * dx), y_km - (ay + t * dy)))
    return best
