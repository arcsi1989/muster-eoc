"""Storm surge and flood depth (plan section 3)."""

import numpy as np

from muster.geo import FloatArray


def local_surge(
    peak_surge_m: float,
    alongshore_km: FloatArray,
    distance_to_coast_km: FloatArray,
    rmax_km: float,
    decay_inland_km: float,
) -> FloatArray:
    """Peak surge, decaying along the coast away from landfall and inland away from the coast."""
    result: FloatArray = (
        peak_surge_m
        * np.exp(-((alongshore_km / (2 * rmax_km)) ** 2))
        * np.exp(-distance_to_coast_km / decay_inland_km)
    )
    return result


def flood_depth(surge_m: FloatArray, elevation_m: FloatArray) -> FloatArray:
    """Water above the site's ground elevation; zero where the ground is above the surge."""
    result: FloatArray = np.maximum(0.0, surge_m - elevation_m)
    return result
