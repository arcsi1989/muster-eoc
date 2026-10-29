"""Lognormal fragility curves with the condition adjustment (plan section 3)."""

import math

import numpy as np

from app.geo import FloatArray


def adjusted_theta(theta: float, condition_score: int, reduction_per_step: float) -> float:
    """Poorer condition lowers the median capacity: theta x (1 - step x (condition - 1))."""
    return theta * (1.0 - reduction_per_step * (condition_score - 1))


def failure_probability(
    intensity: FloatArray, theta: float | FloatArray, beta: float | FloatArray
) -> FloatArray:
    """P(fail | x) = Phi(ln(x / theta) / beta); zero where there is no hazard. theta and beta are
    one curve, or one per intensity."""
    x = np.asarray(intensity, dtype=float)
    with np.errstate(divide="ignore"):
        z = np.where(x > 0, np.log(np.maximum(x, 1e-12) / theta) / beta, -np.inf)
    erf = np.vectorize(math.erf)
    result: FloatArray = np.where(np.isinf(z), 0.0, 0.5 * (1.0 + erf(z / math.sqrt(2.0))))
    return result


def combine(p_wind: FloatArray, p_flood: FloatArray) -> FloatArray:
    """Either hazard can fail the asset: 1 - (1 - p_wind)(1 - p_flood)."""
    result: FloatArray = 1.0 - (1.0 - p_wind) * (1.0 - p_flood)
    return result
