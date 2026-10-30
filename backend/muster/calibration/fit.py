"""Fits the fragility curves to a past storm's failures by MAP (plan M8): the Bernoulli
likelihood of the observed failures, with a lognormal prior on each theta and beta centred on
the prior curves. Deterministic: the same data and prior give the same curves."""

from collections.abc import Sequence

import numpy as np
from scipy.optimize import minimize

from muster.calibration.backtest import Observation, predict
from muster.geo import FloatArray
from muster.models import FragilityCurve

EPSILON = 1e-9  # keeps log(p) finite for a probability of exactly 0 or 1


def fit_map(
    observations: Sequence[Observation],
    prior: Sequence[FragilityCurve],
    reduction_per_step: float,
    prior_sd_log_theta: float,
    prior_sd_log_beta: float,
) -> list[FragilityCurve]:
    """theta and beta for every prior curve. A curve no observation uses keeps its prior."""
    failed = np.array([o.failed for o in observations], dtype=float)
    centre = np.log([v for c in prior for v in (c.theta, c.beta)])
    sd = np.tile([prior_sd_log_theta, prior_sd_log_beta], len(prior))

    def curves(log_params: FloatArray) -> list[FragilityCurve]:
        values = np.exp(log_params)
        return [
            FragilityCurve(
                asset_type=c.asset_type,
                hazard=c.hazard,
                theta=float(values[2 * i]),
                beta=float(values[2 * i + 1]),
            )
            for i, c in enumerate(prior)
        ]

    def negative_log_posterior(log_params: FloatArray) -> float:
        p = np.clip(predict(observations, curves(log_params), reduction_per_step), EPSILON, 1)
        p = np.minimum(p, 1 - EPSILON)
        likelihood = np.sum(failed * np.log(p) + (1 - failed) * np.log(1 - p))
        log_prior = -0.5 * np.sum(((log_params - centre) / sd) ** 2)
        return float(-(likelihood + log_prior))

    result = minimize(negative_log_posterior, centre, method="L-BFGS-B")
    return curves(np.asarray(result.x, dtype=float))
