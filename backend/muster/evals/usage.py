"""What an evaluation run spent: tokens, latency and estimated cost per answer (one run of one
case), summed per run. Read from the grounded generation attempt log, priced with
config/llm.yaml."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from muster.llm.config import LLMConfig, attempt_tokens, total_cost


@dataclass(frozen=True)
class AnswerUsage:
    latency_ms: int  # every attempt at the configured provider, retries included
    tokens_in: int
    tokens_out: int
    cost_usd: float | None  # None: an attempt used tokens of a model with no price


def answer_usage(attempts: list[dict[str, Any]], llm: LLMConfig) -> AnswerUsage:
    """An answer's attempts at the configured provider, each priced at the model that answered
    it. An answer the template wrote outright has no attempts and costs nothing."""
    tokens = [attempt_tokens(a) for a in attempts]
    return AnswerUsage(
        latency_ms=sum(a.get("latency_ms", 0) for a in attempts),
        tokens_in=sum(i for i, _ in tokens),
        tokens_out=sum(o for _, o in tokens),
        cost_usd=llm.attempts_cost(attempts),
    )


def percentile(values: Sequence[int], p: float) -> int:
    """Nearest rank: the smallest value with at least `p` of the values at or below it; 0 for
    no values."""
    if not values:
        return 0
    return sorted(values)[max(math.ceil(p * len(values)), 1) - 1]


@dataclass(frozen=True)
class RunUsage:
    answers: int
    tokens_in: int
    tokens_out: int
    cost_usd: float | None  # None: an answer has no cost estimate
    cost_per_answer_usd: float | None
    latency_p50_ms: int  # per answer
    latency_p90_ms: int


def run_usage(answers: Sequence[AnswerUsage]) -> RunUsage:
    cost = total_cost(a.cost_usd for a in answers)
    latencies = [a.latency_ms for a in answers]
    return RunUsage(
        answers=len(answers),
        tokens_in=sum(a.tokens_in for a in answers),
        tokens_out=sum(a.tokens_out for a in answers),
        cost_usd=cost,
        cost_per_answer_usd=None if cost is None or not answers else cost / len(answers),
        latency_p50_ms=percentile(latencies, 0.5),
        latency_p90_ms=percentile(latencies, 0.9),
    )
