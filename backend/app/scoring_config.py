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
    rank_jump: int
    rank_jump_within: int


class RiskConfig(Strict):
    condition_theta_reduction_per_step: float
    stale_inspection_years: float
    top_n: int
    alert: AlertConfig


class DraftConfig(Strict):
    top_assets: int
    template_top_assets: int
    retrieval_per_query: int
    retrieval_max_clauses: int
    max_tokens: int
    retries: int


class CopilotConfig(Strict):
    max_tool_rounds: int
    history_turns: int
    top_risks_default: int
    top_risks_max: int
    search_results: int
    max_tokens: int
    deadline_s: float
    history_max: int
    retries: int


class CalibrationConfig(Strict):
    storm: str
    reliability_bins: int
    top_fraction: float
    prior_sd_log_theta: float
    prior_sd_log_beta: float


class ScoringConfig(Strict):
    hazard: HazardConfig
    risk: RiskConfig
    draft: DraftConfig
    copilot: CopilotConfig
    calibration: CalibrationConfig
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
