"""Loads config/scoring.yaml: every tunable number for hazard and risk lives there (B9)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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


# Saffir-Simpson category names; their thresholds are config (intensity_min_mph), the names are
# the API contract the frontend mirrors.
IntensityCategory = Literal[
    "tropical_depression", "tropical_storm", "cat_1", "cat_2", "cat_3", "cat_4", "cat_5"
]

# Storm map risk bands, the same way: the names are the API contract, the thresholds are config.
RiskBand = Literal["low", "moderate", "high", "severe"]
RISK_BANDS: tuple[RiskBand, ...] = ("low", "moderate", "high", "severe")


class HazardConfig(Strict):
    wind: WindConfig
    surge: SurgeConfig
    ensemble: EnsembleConfig
    interpolation_step_hours: float
    intensity_min_mph: dict[IntensityCategory, float]  # category -> lowest wind in it


class AlertConfig(Strict):
    risk_threshold: float
    rank_jump: int
    rank_jump_within: int


class RiskConfig(Strict):
    condition_theta_reduction_per_step: float
    stale_inspection_years: float
    top_n: int
    band_min_p_fail: dict[RiskBand, float]  # band -> lowest p_fail in it
    alert: AlertConfig

    @field_validator("band_min_p_fail")
    @classmethod
    def every_band_from_zero_up(cls, bands: dict[RiskBand, float]) -> dict[RiskBand, float]:
        """Every band once, rising thresholds, and the lowest at 0 so every p_fail has a band."""
        thresholds = [bands.get(name, -1.0) for name in RISK_BANDS]
        if thresholds[0] != 0 or thresholds != sorted(thresholds):
            raise ValueError(f"needs {', '.join(RISK_BANDS)} with rising thresholds from 0")
        return bands


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


class PlanningResource(Strict):
    """What one site of a field-work kind needs, and where the stock comes from: an event state
    key (the fuelled generators) or a count per usable staging area (crews)."""

    kind: str
    per_site: int
    stock_state: str | None = None
    per_staging_area: int | None = None

    @model_validator(mode="after")
    def one_stock_source(self) -> "PlanningResource":
        if (self.stock_state is None) == (self.per_staging_area is None):
            raise ValueError("needs exactly one of stock_state and per_staging_area")
        return self


class PlanningConfig(Strict):
    period_hours: int
    max_tokens: int
    retries: int
    resources: dict[str, PlanningResource]  # field-work state key -> resource


CustomerService = Literal["power", "water"]


class FieldNeed(Strict):
    crews: int
    generators: int


class ForecastConfig(Strict):
    """Customers out and field demand per district (ticket 38): failures drawn per ensemble
    member, followed through the dependency graph."""

    draws: int
    seed: int
    supply_lost_share: float
    customers: dict[str, CustomerService]  # asset type -> whose customers its outage counts
    per_failed: dict[str, FieldNeed]  # asset type -> what restoring one failed asset needs
    per_supply_lost: dict[str, FieldNeed]  # asset type -> what one asset out of supply needs

    @model_validator(mode="after")
    def every_type_everywhere(self) -> "ForecastConfig":
        if self.draws < 1 or not 0 < self.supply_lost_share <= 1:
            raise ValueError("needs at least one draw and a supply_lost_share in (0, 1]")
        if not set(self.customers) == set(self.per_failed) == set(self.per_supply_lost):
            raise ValueError("customers, per_failed and per_supply_lost name the same asset types")
        return self


class ScoringConfig(Strict):
    hazard: HazardConfig
    risk: RiskConfig
    draft: DraftConfig
    copilot: CopilotConfig
    calibration: CalibrationConfig
    planning: PlanningConfig
    forecast: ForecastConfig
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
