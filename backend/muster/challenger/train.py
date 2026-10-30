"""Trains the challenger and compares it with the rule-based champion, by storm (CR-03 C2).

Gradient-boosted trees (scikit-learn HistGradientBoostingClassifier) with isotonic calibration
fitted inside the training folds: the calibration only ever sees storms the trees did not train
on. Validation is leave-storms-out cross-validation over the synthetic history; the held-out
storm (Storm Delta) is used once, at the end, for the final comparison, and never in training or
tuning. Permutation importance is measured on each fold's held-out storms.

    uv run python -m muster.challenger.train      (make train)
"""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sqlmodel import Session

from muster.calibration.backtest import BoolArray, evaluate
from muster.challenger.dataset import (
    CATEGORICAL,
    FEATURES,
    StormSample,
    World,
    held_out_storm,
    history_storms,
    stack,
    storm_sample,
)
from muster.challenger.model import Comparison, ModelMetrics, TrainedChallenger, baseline, save
from muster.geo import FloatArray
from muster.ingest.contracts import SyntheticStormFile
from muster.models_config import ChallengerConfig
from muster.scoring_config import ScoringConfig

MODEL_NAME = "challenger-hgb"
RESULTS_FILE = Path("docs") / "eval" / "challenger_results.json"


@dataclass(frozen=True)
class FeatureImportance:
    feature: str
    mean: float  # rise in Brier score when the feature is shuffled, over folds and repeats
    sd: float


@dataclass(frozen=True)
class ChallengerReport:
    model_version: str
    trained_on: list[str]
    held_out: str
    features: list[str]
    cross_validation: Comparison  # pooled out-of-fold predictions over the training storms
    held_out_metrics: Comparison
    importance: list[FeatureImportance]  # highest first
    top_features: list[str]


def build_model(
    features: FloatArray, failed: BoolArray, storms: Sequence[str], config: ChallengerConfig
) -> CalibratedClassifierCV:
    """Fits trees with isotonic calibration on the given rows only. The calibration folds split
    by storm, so each isotonic map is fitted on storms its trees did not see."""
    trees = HistGradientBoostingClassifier(
        **config.hgb.model_dump(),
        categorical_features=list(CATEGORICAL),
        early_stopping=False,
    )
    splits = list(GroupKFold(config.calibration_folds).split(features, failed, storms))
    model = CalibratedClassifierCV(trees, method="isotonic", cv=splits)
    model.fit(features, failed)
    return model


def failure_probability(model: CalibratedClassifierCV, features: FloatArray) -> FloatArray:
    p: FloatArray = model.predict_proba(features)[:, 1]
    return p


def metrics(p: FloatArray, failed: BoolArray, scoring: ScoringConfig) -> ModelMetrics:
    """The calibration back-test's metrics (same bins and top fraction) plus ROC AUC."""
    base = evaluate(
        p, failed, scoring.calibration.reliability_bins, scoring.calibration.top_fraction
    )
    auc = float(roc_auc_score(failed, p)) if 0 < failed.sum() < len(failed) else None
    fields = {f.name: getattr(base, f.name) for f in dataclass_fields(base)}  # bins stay bins
    return ModelMetrics(**fields, roc_auc=auc)


def cross_validate(
    samples: Sequence[StormSample], scoring: ScoringConfig, config: ChallengerConfig
) -> tuple[Comparison, list[FeatureImportance]]:
    """Leave-storms-out: each fold trains (and calibrates) on the other storms and predicts its
    own. Returns metrics on the pooled out-of-fold predictions and the permutation importance
    measured on each fold's held-out storms."""
    features, failed, champion_p, storms = stack(samples)
    out_of_fold = np.zeros(len(failed))
    drops: list[FloatArray] = []  # one row per fold and repeat
    for train, test in GroupKFold(config.cv_folds).split(features, failed, storms):
        model = build_model(features[train], failed[train], [storms[i] for i in train], config)
        out_of_fold[test] = failure_probability(model, features[test])
        importance = permutation_importance(
            model,
            features[test],
            failed[test],
            scoring="neg_brier_score",
            n_repeats=config.permutation_repeats,
            random_state=config.hgb.random_state,
        )
        drops.extend(np.asarray(importance.importances).T)
    table = np.array(drops)
    ranked = sorted(
        (
            FeatureImportance(name, float(table[:, i].mean()), float(table[:, i].std()))
            for i, name in enumerate(FEATURES)
        ),
        key=lambda f: -f.mean,
    )
    comparison = Comparison(
        challenger=metrics(out_of_fold, failed, scoring),
        champion=metrics(champion_p, failed, scoring),
    )
    return comparison, ranked


def run(
    session: Session,
    world: World,
    history: Sequence[SyntheticStormFile],
    scoring: ScoringConfig,
    config: ChallengerConfig,
) -> tuple[ChallengerReport, TrainedChallenger]:
    """Cross-validates on the history, trains the final model on all of it and compares both
    models on the held-out storm. Returns the report and the final model."""
    held_out_name = scoring.calibration.storm
    storms = history_storms(history)
    if any(s.name == held_out_name for s in storms):
        raise ValueError(f"{held_out_name} is the held-out storm; it cannot be in the history")
    offset = config.ensemble_seed_offset
    samples = [
        storm_sample(storm, offset + 1 + i, world, scoring, config)
        for i, storm in enumerate(storms)
    ]
    held_out = storm_sample(held_out_storm(session, held_out_name), offset, world, scoring, config)

    cv, importance = cross_validate(samples, scoring, config)
    features, failed, _, groups = stack(samples)
    model = build_model(features, failed, groups, config)
    held_out_metrics = Comparison(
        challenger=metrics(failure_probability(model, held_out.features), held_out.failed, scoring),
        champion=metrics(held_out.champion_p, held_out.failed, scoring),
    )
    name = f"{MODEL_NAME}-{len(storms)}storms-seed{config.hgb.random_state}"
    report = ChallengerReport(
        model_version=name,
        trained_on=[s.name for s in storms],
        held_out=held_out_name,
        features=list(FEATURES),
        cross_validation=cv,
        held_out_metrics=held_out_metrics,
        importance=importance,
        top_features=[f.feature for f in importance[: config.top_features]],
    )
    return report, TrainedChallenger(
        name, model, baseline(features), held_out_name, held_out_metrics
    )


def write_report(report: ChallengerReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_rounded(asdict(report)), indent=2) + "\n")


def _rounded(value: Any) -> Any:
    """Six decimals: the results file stays readable and stable in diffs."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def summary(report: ChallengerReport) -> str:
    lines = [f"{report.model_version}: trained on {len(report.trained_on)} storms"]
    for label, comparison in (
        ("Leave-storms-out CV", report.cross_validation),
        (f"Held out: {report.held_out}", report.held_out_metrics),
    ):
        lines.append(f"{label}:")
        for name, m in (("challenger", comparison.challenger), ("champion", comparison.champion)):
            auc = "n/a" if m.roc_auc is None else f"{m.roc_auc:.3f}"
            lines.append(
                f"  {name:<10} Brier {m.brier:.4f}  ROC AUC {auc}  "
                f"top-decile capture {m.top_capture:.2f}  ({m.failures}/{m.assets} failed)"
            )
    lines.append("Permutation importance (rise in Brier score when shuffled):")
    lines += [f"  {f.feature:<22} {f.mean:+.5f} ± {f.sd:.5f}" for f in report.importance]
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
        result, trained = run(
            db, load_world(db, scoring_config), storms_file, scoring_config, challenger_config
        )
    write_report(result, REPO_ROOT / RESULTS_FILE)
    save(trained, settings.challenger_model_path)
    print(summary(result))
    print(f"Results written: {RESULTS_FILE}; model saved: {settings.challenger_model_path}")
