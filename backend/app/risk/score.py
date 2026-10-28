"""Placeholder score for the walking skeleton: closeness to the forecast landfall point.

Replaced by the risk score (p_fail x consequence) in ticket 04.
"""

import math

PLACEHOLDER_REACH_KM = 150.0


def placeholder_score(
    x_km: float, y_km: float, landfall_x_km: float, landfall_y_km: float
) -> float:
    distance = math.hypot(x_km - landfall_x_km, y_km - landfall_y_km)
    return round(max(0.0, 1.0 - distance / PLACEHOLDER_REACH_KM), 3)
