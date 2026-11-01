"""How bad, where, and is there enough: customers out and field demand per district (ticket 38).

Each ensemble member gives every asset a failure probability under that member's hazard. A
member's failures are drawn from them (`draws` times, seeded) and followed through the
dependency graph: an asset with feeders is out once at least `supply_lost_share` of them is out,
so a pumping station goes down with its substation and the treatment plant with the pumping
stations that feed it. Every draw of every member is one sample, each member weighted the same;
each figure is the median and the P90 over the samples, taken as sample values so a count
stays a whole number. Deterministic code only: no model
computes or changes any of it."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import get_args

import numpy as np

from muster.calibration.backtest import BoolArray
from muster.geo import FloatArray
from muster.risk.model import AssetFeatures
from muster.scoring_config import CustomerService, ForecastConfig


@dataclass(frozen=True)
class ForecastAsset:
    id: str
    type: str
    district: str
    customers_served: int

    @classmethod
    def of(cls, features: AssetFeatures) -> "ForecastAsset":
        a = features.asset
        return cls(a.id, a.type, a.district, a.customers_served)


@dataclass(frozen=True)
class Spread:
    """The median and the P90 of a figure over the samples."""

    p50: float
    p90: float


@dataclass(frozen=True)
class DistrictForecast:
    """What the expected failures in one district would mean, before any playbook action."""

    district: str
    power_customers: Spread
    water_customers: Spread
    crews: Spread
    generators: Spread
    failed_assets: Spread


@dataclass(frozen=True)
class DistrictOutcome:
    """The same figures for one known set of failures (a past storm's)."""

    district: str
    power_customers: float
    water_customers: float
    crews: float
    generators: float
    failed_assets: float


def forecast(
    assets: Sequence[ForecastAsset],
    fed_by: Mapping[str, Sequence[str]],
    member_p: FloatArray,
    districts: Sequence[str],
    config: ForecastConfig,
    seed: int,
) -> list[DistrictForecast]:
    """`member_p` is members x assets, in the order of `assets`. One forecast per district, in
    the order of `districts`."""
    members, n = member_p.shape
    if n != len(assets):
        raise ValueError(f"member_p has {n} assets, expected {len(assets)}")
    rng = np.random.default_rng(seed)
    draws = rng.random((members, config.draws, n)) < member_p[:, None, :]
    totals = _district_totals(assets, fed_by, draws.reshape(-1, n), districts, config)

    def spread(values: FloatArray) -> Spread:
        p50, p90 = np.percentile(values, [50, 90], method="higher")  # whole samples
        return Spread(float(p50), float(p90))

    return [
        DistrictForecast(name, *(spread(t[:, i]) for t in totals))
        for i, name in enumerate(districts)
    ]


def outcome(
    assets: Sequence[ForecastAsset],
    fed_by: Mapping[str, Sequence[str]],
    failed: Mapping[str, bool],
    districts: Sequence[str],
    config: ForecastConfig,
) -> list[DistrictOutcome]:
    """The figures for the failures that happened: an asset not in `failed` did not fail."""
    sample = np.array([[failed.get(a.id, False) for a in assets]])
    totals = _district_totals(assets, fed_by, sample, districts, config)
    return [
        DistrictOutcome(name, *(float(t[0, i]) for t in totals)) for i, name in enumerate(districts)
    ]


def out_of_service(
    assets: Sequence[ForecastAsset],
    fed_by: Mapping[str, Sequence[str]],
    failed: BoolArray,
    share: float,
) -> BoolArray:
    """samples x assets: failed, or out because at least `share` of its feeders are out,
    followed until nothing changes (the graph has no cycles, so this ends)."""
    index = {a.id: i for i, a in enumerate(assets)}
    fed = [
        (index[a.id], [index[f] for f in fed_by[a.id] if f in index])
        for a in assets
        if fed_by.get(a.id)
    ]
    out = failed.copy()
    for _ in range(len(assets)):
        before = out.copy()
        for target, feeders in fed:
            if feeders:
                out[:, target] |= out[:, feeders].mean(axis=1) >= share
        if np.array_equal(out, before):
            break
    return out


def _district_totals(
    assets: Sequence[ForecastAsset],
    fed_by: Mapping[str, Sequence[str]],
    failed: BoolArray,
    districts: Sequence[str],
    config: ForecastConfig,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    """samples x districts: power customers, water customers, crews, generators, failed assets."""
    out = out_of_service(assets, fed_by, failed, config.supply_lost_share)
    supply_lost = out & ~failed
    in_district = np.array([[a.district == d for d in districts] for a in assets], dtype=float)

    def per_asset(values: list[float]) -> FloatArray:
        weights: FloatArray = np.array(values, dtype=float)[:, None] * in_district
        return weights

    customers = {
        service: per_asset(
            [a.customers_served if config.customers[a.type] == service else 0 for a in assets]
        )
        for service in get_args(CustomerService)
    }
    crews_failed = per_asset([config.per_failed[a.type].crews for a in assets])
    crews_lost = per_asset([config.per_supply_lost[a.type].crews for a in assets])
    gens_failed = per_asset([config.per_failed[a.type].generators for a in assets])
    gens_lost = per_asset([config.per_supply_lost[a.type].generators for a in assets])
    f, lost, o = failed.astype(float), supply_lost.astype(float), out.astype(float)
    return (
        o @ customers["power"],
        o @ customers["water"],
        f @ crews_failed + lost @ crews_lost,
        f @ gens_failed + lost @ gens_lost,
        f @ in_district,
    )
