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


class ScoringConfig(Strict):
    hazard: HazardConfig


def load_scoring_config(path: Path) -> ScoringConfig:
    return ScoringConfig.model_validate(yaml.safe_load(path.read_text()))
