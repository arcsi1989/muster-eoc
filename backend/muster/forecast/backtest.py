"""Back-tests the outage forecast on the synthetic storm history (ticket 38): for each past
storm, the forecast per district (the same ensemble the challenger's features use, the
published curves, the configured draws) against what the storm's simulated failures did,
followed through the same dependency graph. Storm Delta is held out and reported on its own,
as for the challenger. The forecast fits nothing, so the history is not training data: it is
the larger sample the forecast's behaviour is measured on, and Storm Delta the one the
configured numbers were never looked at against.

Accuracy here shows the discipline, not skill on SGW: the history is synthetic, and its
outcomes come from a hidden truth this repo also wrote (docs/assumptions_limitations.md).

    uv run python -m muster.forecast.backtest      (make forecast-backtest)
"""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean

from sqlmodel import Session

from muster.challenger.dataset import (
    PastStorm,
    World,
    held_out_storm,
    history_storms,
    published_rules,
    storm_assets,
)
from muster.forecast.model import ForecastAsset, forecast, outcome
from muster.forecast.service import district_names
from muster.ingest.contracts import SyntheticStormFile
from muster.models_config import ChallengerConfig
from muster.numbers import rounded
from muster.scoring_config import ScoringConfig

RESULTS_FILE = Path("docs") / "eval" / "forecast_results.json"
FIGURES = ("power_customers", "water_customers", "crews", "generators")


@dataclass(frozen=True)
class FigureResult:
    observed: float
    p50: float
    p90: float


@dataclass(frozen=True)
class DistrictResult:
    district: str
    figures: dict[str, FigureResult]


@dataclass(frozen=True)
class StormResult:
    storm: str
    held_out: bool
    districts: list[DistrictResult]


@dataclass(frozen=True)
class FigureMetrics:
    """One figure over storms x districts."""

    cases: int
    p90_coverage: float  # share of cases whose observed value is at most the P90
    p50_mean_abs_error: float
    p50_mean_bias: float  # forecast minus observed: below zero, the median forecasts too few
    observed_total: float
    p50_total: float


@dataclass(frozen=True)
class ForecastBacktest:
    history: list[str]
    held_out: str
    draws: int
    samples: int  # per storm: ensemble members x draws
    storms: list[StormResult]
    history_metrics: dict[str, FigureMetrics]
    held_out_metrics: dict[str, FigureMetrics]


def storm_result(
    storm: PastStorm,
    seed_index: int,
    held_out: bool,
    world: World,
    districts: Sequence[str],
    scoring: ScoringConfig,
    challenger: ChallengerConfig,
) -> StormResult:
    """The forecast and the simulated outcome of one storm, district by district."""
    assets = storm_assets(storm, seed_index, world, scoring, challenger)
    forecast_assets = [
        ForecastAsset(a.asset.id, a.asset.type, a.asset.district, a.asset.customers_served)
        for a in assets
    ]
    fed_by = world.network.fed_by
    member_p = published_rules(world, scoring).member_p_fail(assets)
    config = scoring.forecast
    predicted = forecast(
        forecast_assets, fed_by, member_p, districts, config, config.seed + seed_index
    )
    observed = outcome(forecast_assets, fed_by, storm.failed, districts, config)
    return StormResult(
        storm=storm.name,
        held_out=held_out,
        districts=[
            DistrictResult(
                district=p.district,
                figures={
                    name: FigureResult(getattr(o, name), getattr(p, name).p50, getattr(p, name).p90)
                    for name in FIGURES
                },
            )
            for p, o in zip(predicted, observed, strict=True)
        ],
    )


def figure_metrics(results: Sequence[StormResult]) -> dict[str, FigureMetrics]:
    def metrics(name: str) -> FigureMetrics:
        cases = [d.figures[name] for r in results for d in r.districts]
        return FigureMetrics(
            cases=len(cases),
            p90_coverage=fmean(c.observed <= c.p90 for c in cases),
            p50_mean_abs_error=fmean(abs(c.p50 - c.observed) for c in cases),
            p50_mean_bias=fmean(c.p50 - c.observed for c in cases),
            observed_total=sum(c.observed for c in cases),
            p50_total=sum(c.p50 for c in cases),
        )

    return {name: metrics(name) for name in FIGURES}


def run(
    session: Session,
    world: World,
    history: Sequence[SyntheticStormFile],
    scoring: ScoringConfig,
    challenger: ChallengerConfig,
) -> ForecastBacktest:
    """Each storm uses the challenger's ensemble seed for it, so both back-tests see the same
    exposure; the forecast's draws are seeded with its own seed plus the same index."""
    held_out_name = scoring.calibration.storm
    storms = history_storms(history)
    if any(s.name == held_out_name for s in storms):
        raise ValueError(f"{held_out_name} is the held-out storm; it cannot be in the history")
    districts = district_names(session)
    offset = challenger.ensemble_seed_offset
    past = [
        storm_result(s, offset + 1 + i, False, world, districts, scoring, challenger)
        for i, s in enumerate(storms)
    ]
    delta = storm_result(
        held_out_storm(session, held_out_name), offset, True, world, districts, scoring, challenger
    )
    members = scoring.hazard.ensemble.members
    return ForecastBacktest(
        history=[s.name for s in storms],
        held_out=held_out_name,
        draws=scoring.forecast.draws,
        samples=members * scoring.forecast.draws,
        storms=[*past, delta],
        history_metrics=figure_metrics(past),
        held_out_metrics=figure_metrics([delta]),
    )


def write_report(report: ForecastBacktest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rounded(asdict(report)), indent=2) + "\n")


def summary(report: ForecastBacktest) -> str:
    lines = [f"Outage forecast back-test: {len(report.history)} storms, {report.samples} samples"]
    for label, metrics in (
        ("History", report.history_metrics),
        (f"Held out: {report.held_out}", report.held_out_metrics),
    ):
        lines.append(f"{label}:")
        lines += [
            f"  {name:<16} P90 covers {m.p90_coverage:.0%} of {m.cases}  "
            f"P50 error {m.p50_mean_abs_error:,.0f}  bias {m.p50_mean_bias:+,.0f}  "
            f"(observed {m.observed_total:,.0f}, P50 {m.p50_total:,.0f})"
            for name, m in metrics.items()
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    from sqlmodel import SQLModel, create_engine

    from muster.challenger.dataset import load_world
    from muster.config import REPO_ROOT, get_settings
    from muster.datagen.history import HISTORY_FILE
    from muster.ingest.loader import load_gold
    from muster.models_config import load_models_config
    from muster.scoring_config import load_scoring_config

    settings = get_settings()
    scoring_config = load_scoring_config(settings.scoring_config_path)
    challenger_config = load_models_config(settings.models_config_path).challenger
    storms_file = [
        SyntheticStormFile.model_validate(s) for s in json.loads(HISTORY_FILE.read_text())
    ]
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        load_gold(db, settings.data_dir)
        result = run(
            db, load_world(db, scoring_config), storms_file, scoring_config, challenger_config
        )
    write_report(result, REPO_ROOT / RESULTS_FILE)
    print(summary(result))
    print(f"Results written: {RESULTS_FILE}")
