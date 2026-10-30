"""Wind field: modified Rankine vortex (plan section 3)."""

import numpy as np

from muster.geo import FloatArray


def rankine_wind(
    r_km: FloatArray, vmax_mph: FloatArray | float, rmax_km: FloatArray | float, alpha: float
) -> FloatArray:
    """Sustained wind at distance r from the storm centre: rises linearly to Vmax at Rmax, then
    decays as (Rmax / r)^alpha."""
    r = np.asarray(r_km, dtype=float)
    inside = vmax_mph * r / rmax_km
    outside = vmax_mph * (rmax_km / np.maximum(r, 1e-9)) ** alpha
    result: FloatArray = np.where(r < rmax_km, inside, outside)
    return result
