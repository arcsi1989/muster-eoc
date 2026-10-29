"""Loads config/scoring.yaml: every tunable number for hazard and risk lives there (B9)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WindConfig(Strict):
    alpha: float
    inland_decay_factor: float
    inland_decay_km: float
    tropical_storm_force_mph: float


class SurgeConfig(Strict):
    decay_inland_km: float
    imputation_neighbours: int


class EnsembleConfig(Strict):
    members: int
    sigma_cone_factor: float
    seed: int


class HazardConfig(Strict):
    wind: WindConfig
    surge: SurgeConfig
    ensemble: EnsembleConfig
    interpolation_step_hours: float


class AlertConfig(Strict):
    risk_threshold: float
    top_n: int
    rank_jump: int
    rank_jump_within: int


class RiskConfig(Strict):
    condition_theta_reduction_per_step: float
    stale_inspection_years: float
    alert: AlertConfig


class ScoringConfig(Strict):
    hazard: HazardConfig
    risk: RiskConfig
    consequence_weights: dict[str, float]  # from consequence_weights.yaml


def load_scoring_config(path: Path, weights_path: Path | None = None) -> ScoringConfig:
    """Reads scoring.yaml and, next to it, consequence_weights.yaml."""
    weights_path = weights_path or path.with_name("consequence_weights.yaml")
    return ScoringConfig.model_validate(
        {
            **yaml.safe_load(path.read_text()),
            "consequence_weights": yaml.safe_load(weights_path.read_text()),
        }
    )
