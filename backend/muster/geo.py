"""Geometry on the planar km grid of the fictional territory."""

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

Point = tuple[float, float]
FloatArray = NDArray[np.float64]


def distance_to_polyline(x_km: float, y_km: float, polyline: Sequence[Point]) -> float:
    """Shortest distance from a point to a polyline, in km."""
    distances, _ = project_onto_polyline(np.array([[x_km, y_km]]), polyline)
    return float(distances[0])


def project_onto_polyline(
    points: FloatArray, polyline: Sequence[Point]
) -> tuple[FloatArray, FloatArray]:
    """For each point (N x 2): distance to the polyline and arclength of the nearest point on it."""
    line = np.asarray(polyline, dtype=float)
    a, b = line[:-1], line[1:]
    seg = b - a
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    start = np.concatenate([[0.0], np.cumsum(seg_len)[:-1]])
    rel = points[:, None, :] - a[None, :, :]  # N x S x 2
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(seg_len > 0, (rel * seg[None]).sum(axis=2) / seg_len**2, 0.0)
    t = np.clip(t, 0.0, 1.0)
    nearest = a[None] + t[..., None] * seg[None]
    dist = np.hypot(*(points[:, None, :] - nearest).transpose(2, 0, 1))
    best = dist.argmin(axis=1)
    rows = np.arange(len(points))
    return dist[rows, best], start[best] + t[rows, best] * seg_len[best]


def boundary_inland(x_km: float, coastline: Sequence[Point], land: Sequence[Point]) -> list[Point]:
    """A north-south line at x_km from the coast (west-to-east coastline) to the land's northern
    edge: where two neighbouring districts meet."""
    line = np.asarray(coastline, dtype=float)
    coast_y = float(np.interp(x_km, line[:, 0], line[:, 1]))
    return [(x_km, coast_y), (x_km, max(y for _, y in land))]


def inside_polygon(points: FloatArray, polygon: Sequence[Point]) -> NDArray[np.bool_]:
    """Ray casting: True for each point (N x 2) inside the polygon."""
    poly = np.asarray(polygon, dtype=float)
    x, y = points[:, 0][:, None], points[:, 1][:, None]
    x1, y1 = poly[:, 0][None], poly[:, 1][None]
    x2, y2 = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    crosses = (y1 > y) != (y2 > y)
    with np.errstate(invalid="ignore", divide="ignore"):
        x_at = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
    result: NDArray[np.bool_] = ((crosses & (x < x_at)).sum(axis=1) % 2) == 1
    return result


def heading_unit_vector(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length
