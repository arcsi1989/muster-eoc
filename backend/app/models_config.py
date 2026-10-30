"""Loads config/models.yaml: the synthetic storm history and the challenger model (CR-03 C2)."""

from pathlib import Path

import yaml
from pydantic import model_validator

from app.scoring_config import Strict

Range = tuple[float, float]


class AgeConditionEffect(Strict):
    """The hidden effect the rule-based score does not model: assets older than `min_age_years`
    with a condition score of at least `min_condition_score` fail more often under wind of at
    least `min_wind_mph`, and more still when flood of at least `min_flood_m` comes with it."""

    min_age_years: int
    min_condition_score: int
    min_wind_mph: float
    extra_failure_probability: float
    min_flood_m: float
    extra_failure_probability_flooded: float


class HistoryConfig(Strict):
    seed: int
    storms: int
    year_range: tuple[int, int]
    landfall_x_km: Range
    heading_deg_from_east: Range
    vmax_mph: Range
    peak_surge_m: Range
    rmax_km: Range
    hours_before_landfall: int
    age_condition_effect: AgeConditionEffect


class HgbConfig(Strict):
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int


class ChallengerConfig(Strict):
    forecast_cone_radius_km: float
    ensemble_seed_offset: int
    cv_folds: int
    calibration_folds: int
    permutation_repeats: int
    top_features: int
    hgb: HgbConfig

    @model_validator(mode="after")
    def folds_split_storms(self) -> "ChallengerConfig":
        if self.cv_folds < 2 or self.calibration_folds < 2:
            raise ValueError("cv_folds and calibration_folds need at least 2 folds each")
        return self


class PromotionRule(Strict):
    """When the challenger may be proposed: on the held-out storm it beats the champion by both
    margins and its calibration error is at most `max_calibration_error`."""

    min_brier_improvement: float
    min_top_capture_gain: float
    max_calibration_error: float


class ModelsConfig(Strict):
    history: HistoryConfig
    challenger: ChallengerConfig
    promotion: PromotionRule


def load_models_config(path: Path) -> ModelsConfig:
    return ModelsConfig.model_validate(yaml.safe_load(path.read_text()))
