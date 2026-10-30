"""Loads config/llm.yaml: the model prices the run trace estimates cost with (B9)."""

from pathlib import Path

import yaml

from muster.scoring_config import Strict


class Price(Strict):
    input: float  # USD per million input tokens
    output: float  # USD per million output tokens


class LLMConfig(Strict):
    prices_usd_per_mtok: dict[str, Price]

    def cost_usd(self, model: str | None, tokens_in: int, tokens_out: int) -> float | None:
        """The estimated cost of one call: zero without tokens (the template), None for a model
        with tokens but no price."""
        if not tokens_in and not tokens_out:
            return 0.0
        price = self.prices_usd_per_mtok.get(model or "")
        if price is None:
            return None
        return (tokens_in * price.input + tokens_out * price.output) / 1_000_000


def load_llm_config(path: Path) -> LLMConfig:
    return LLMConfig.model_validate(yaml.safe_load(path.read_text()))
