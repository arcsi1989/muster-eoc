"""The challenger model (CR-03 C2): the synthetic storm history, leave-storms-out training with
in-fold calibration, and the held-out comparison with the rule-based champion. Training uses a
fixed slice of the history so the suite stays fast."""

import json
from typing import Any

import pytest

from app.challenger.dataset import FEATURES, history_storms, load_world, storm_sample
from app.challenger.train import cross_validate, run
from app.config import REPO_ROOT
from app.datagen.history import HISTORY_FILE, build_history
from app.datagen.truth import extra_failure_probability
from app.ingest.contracts import SyntheticStormFile
from app.models_config import ChallengerConfig, HistoryConfig, load_models_config
from app.scoring_config import load_scoring_config
from tests.conftest import SeededScenario

GOLD = REPO_ROOT / "data" / "gold"
MODELS = load_models_config(REPO_ROOT / "config" / "models.yaml")
SCORING = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
EFFECT = MODELS.history.age_condition_effect
SLICE = 8  # storms of the history the tests train on

# Fewer folds, repeats and trees than `make train`: the same discipline, a few seconds.
FAST = MODELS.challenger.model_copy(
    update={
        "cv_folds": 3,
        "calibration_folds": 2,
        "permutation_repeats": 3,
        "hgb": MODELS.challenger.hgb.model_copy(update={"max_iter": 100}),
    }
)


def gold(name: str) -> Any:
    return json.loads((GOLD / name).read_text())


def committed_history() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads(HISTORY_FILE.read_text())
    return result


def history_slice() -> list[SyntheticStormFile]:
    return [SyntheticStormFile.model_validate(s) for s in committed_history()[:SLICE]]


def asset(install_year: int, condition_score: int) -> dict[str, Any]:
    return {"install_year": install_year, "condition_score": condition_score}


def test_the_effect_needs_an_old_asset_in_poor_condition_under_strong_wind() -> None:
    old_poor = asset(2026 - EFFECT.min_age_years - 1, EFFECT.min_condition_score)
    wind = EFFECT.min_wind_mph
    assert extra_failure_probability(old_poor, wind, 0.0, EFFECT, 2026) == (
        EFFECT.extra_failure_probability
    )
    assert extra_failure_probability(old_poor, wind, EFFECT.min_flood_m, EFFECT, 2026) == (
        EFFECT.extra_failure_probability_flooded
    )
    assert extra_failure_probability(old_poor, wind - 1, 1.0, EFFECT, 2026) == 0.0
    young_poor = asset(2026 - EFFECT.min_age_years, EFFECT.min_condition_score)
    assert extra_failure_probability(young_poor, wind, 1.0, EFFECT, 2026) == 0.0
    old_fair = asset(1950, EFFECT.min_condition_score - 1)
    assert extra_failure_probability(old_fair, wind, 1.0, EFFECT, 2026) == 0.0


def small_history(config: HistoryConfig) -> list[dict[str, Any]]:
    return build_history(gold("assets.json"), gold("coastline.geojson"), config, SCORING)


def test_the_history_is_reproducible_and_matches_the_committed_file() -> None:
    config = MODELS.history.model_copy(update={"storms": 2})
    first = small_history(config)
    assert small_history(config) == first
    assert first == committed_history()[:2]  # make history writes the same storms
    committed = committed_history()
    assert len(committed) == MODELS.history.storms
    assert SCORING.calibration.storm not in {s["name"] for s in committed}


def test_the_age_condition_effect_changes_only_old_poor_assets_outcomes() -> None:
    """The effect lives in the simulated outcomes only: without it the same storms are drawn and
    every asset that is not old and in poor condition keeps its outcome."""
    with_effect = small_history(MODELS.history.model_copy(update={"storms": 4}))
    no_effect = MODELS.history.model_copy(
        update={
            "storms": 4,
            "age_condition_effect": EFFECT.model_copy(
                update={"extra_failure_probability": 0.0, "extra_failure_probability_flooded": 0.0}
            ),
        }
    )
    without = small_history(no_effect)
    assets = {a["id"]: a for a in gold("assets.json")}
    changed = set()
    for a, b in zip(with_effect, without, strict=True):
        assert a["track"] == b["track"]
        for x, y in zip(a["outcomes"], b["outcomes"], strict=True):
            if x["failed"] != y["failed"]:
                changed.add(x["asset_id"])
                assert x["failed"]  # the effect only adds failures
    assert changed
    for asset_id in changed:
        a = assets[asset_id]
        assert 2026 - a["install_year"] > EFFECT.min_age_years
        assert a["condition_score"] >= EFFECT.min_condition_score
    assert not any("age" in f and "condition" in f for f in FEATURES)  # no interaction feature


def test_training_holds_storm_delta_out_and_reports_both_models(seeded: SeededScenario) -> None:
    world = load_world(seeded.session, SCORING)
    report, _ = run(seeded.session, world, history_slice(), SCORING, FAST)

    assert report.held_out == "Storm Delta"
    assert report.trained_on == [s.name for s in history_slice()]
    assert "Storm Delta" not in report.trained_on
    for comparison in (report.cross_validation, report.held_out_metrics):
        for m in (comparison.challenger, comparison.champion):
            assert 0 <= m.brier <= 1
            assert m.roc_auc is not None and 0 <= m.roc_auc <= 1
            assert 0 <= m.top_capture <= 1
            assert len(m.reliability) == SCORING.calibration.reliability_bins
    delta = report.held_out_metrics
    assert delta.challenger.assets == delta.champion.assets == 196
    assert delta.challenger.failures == delta.champion.failures
    assert report.cross_validation.challenger.assets == 196 * SLICE
    assert {f.feature for f in report.importance} == set(FEATURES)


def test_storm_delta_cannot_be_trained_on(seeded: SeededScenario) -> None:
    storms = history_slice()
    storms[0] = storms[0].model_copy(update={"name": "Storm Delta"})
    with pytest.raises(ValueError, match="held-out"):
        run(seeded.session, load_world(seeded.session, SCORING), storms, SCORING, FAST)


def importance_of(seeded: SeededScenario, storms: list[SyntheticStormFile]) -> dict[str, float]:
    world = load_world(seeded.session, SCORING)
    samples = [
        storm_sample(s, i, world, SCORING, FAST) for i, s in enumerate(history_storms(storms))
    ]
    _, importance = cross_validate(samples, SCORING, FAST)
    return {f.feature: f.mean for f in importance}


def top(importance: dict[str, float], config: ChallengerConfig) -> list[str]:
    return sorted(importance, key=lambda f: -importance[f])[: config.top_features]


def test_the_challenger_finds_the_age_condition_effect(seeded: SeededScenario) -> None:
    """Age and condition both rank among the challenger's top features (permutation importance
    on held-out storms). Age matters only through the effect: without it, age drops away."""
    found = importance_of(seeded, history_slice())
    assert {"age_years", "condition_score"} <= set(top(found, FAST))

    no_effect = MODELS.history.model_copy(
        update={
            "storms": SLICE,
            "age_condition_effect": EFFECT.model_copy(
                update={"extra_failure_probability": 0.0, "extra_failure_probability_flooded": 0.0}
            ),
        }
    )
    control = [SyntheticStormFile.model_validate(s) for s in small_history(no_effect)]
    assert importance_of(seeded, control)["age_years"] < found["age_years"] / 2
