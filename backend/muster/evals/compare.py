"""Which model is good enough, at what cost: the golden set against each model of the configured
provider, ranked (`make eval-compare`).

    uv run python -m muster.evals.compare

Runs the suite with the live repeats once per model in config/evals.yaml (`compare.models`) and
writes comparison.md and comparison.json (default docs/eval/), with each model's full results and
report under comparison/<model>/. Per model: pass rate per category and the gate, median and P90
latency per answer, tokens, and the cost per answer and per run at config/llm.yaml prices. It
reports and does not gate: it exits 0 once the comparison is written. A live run costs API money.
"""

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from muster.config import Settings, get_settings
from muster.evals import report
from muster.evals.golden import (
    CATEGORIES,
    EvalConfig,
    GoldenSet,
    load_eval_config,
    load_golden,
    verdict,
)
from muster.evals.run import EVAL_CONFIG, GOLDEN, OUT, Evaluation, evaluate, write
from muster.evals.usage import RunUsage
from muster.llm.factory import LLMConfigError, build_provider
from muster.llm.provider import LLMProvider
from muster.scoring_config import load_scoring_config

Providers = Callable[[str], LLMProvider]  # the provider that answers with a given model


class CompareError(RuntimeError):
    """The configured provider has no models to compare, or cannot be built."""


@dataclass(frozen=True)
class ModelResult:
    model: str
    evaluation: Evaluation

    @property
    def usage(self) -> RunUsage:
        return self.evaluation.usage

    @property
    def pass_rate(self) -> float:
        """Every passed run over every run, all categories together."""
        summary = self.evaluation.summary.values()
        runs = sum(s.runs for s in summary)
        return sum(s.passed for s in summary) / runs if runs else 0.0


def _rank_key(result: ModelResult) -> tuple[float, ...]:
    """Models that pass the gate first, cheapest per answer first (no price last), then by pass
    rate and median latency; then the others, best pass rate first, then cheapest."""
    cost = result.usage.cost_per_answer_usd
    priced = (float(cost is None), cost or 0.0)
    latency = float(result.usage.latency_p50_ms)
    if result.evaluation.gate_passed:
        return (0.0, *priced, -result.pass_rate, latency)
    return (1.0, -result.pass_rate, *priced, latency)


def rank(results: Sequence[ModelResult]) -> list[ModelResult]:
    return sorted(results, key=_rank_key)


def compare(
    golden: GoldenSet, config: EvalConfig, providers: Providers, settings: Settings
) -> list[ModelResult]:
    """The golden set with each model in `config.compare`, live repeats, ranked."""
    return rank(
        [
            ModelResult(model, evaluate(golden, config, providers(model), settings, live=True))
            for model in config.compare.models
        ]
    )


def live_providers(settings: Settings, models: list[str]) -> Providers:
    """The configured provider once per model, built before any run, so a missing key or a
    provider without models stops the comparison before it spends anything."""
    if settings.llm_provider == "template":
        raise CompareError(
            "LLM_PROVIDER=template has no models to compare: set LLM_PROVIDER to a live provider "
            "and its API key (a live comparison costs API money)."
        )
    scoring = load_scoring_config(settings.scoring_config_path)
    built: dict[str, LLMProvider] = {}
    for model in models:
        try:
            provider = build_provider(settings.model_copy(update={"llm_model": model}), scoring)
        except LLMConfigError as error:
            raise CompareError(str(error)) from error
        if provider.model is None:
            raise CompareError(f"the {provider.name} provider has no models to compare")
        built[model] = provider
    return built.__getitem__


def _folder(model: str) -> str:
    return re.sub(r"[^\w.-]", "_", model)


def to_json(results: Sequence[ModelResult], golden: GoldenSet) -> dict[str, Any]:
    """`results`: at least one model (config/evals.yaml requires one); the runs share their
    provider, prompts, commit and repeats."""
    passing = [r for r in results if r.evaluation.gate_passed]
    stamp = results[0].evaluation.stamp
    return {
        "stamp": {
            "provider": stamp.provider,
            "prompt_versions": stamp.prompt_versions,
            "git_commit": stamp.git_commit,
            "repeats": stamp.repeats,
            "cases": len(golden.cases),
        },
        "recommended": passing[0].model if passing else None,
        "models": [
            {
                "rank": n,
                "model": r.model,
                "gate_passed": r.evaluation.gate_passed,
                "pass_rate": r.pass_rate,
                "summary": {c: asdict(s) for c, s in r.evaluation.summary.items()},
                "usage": asdict(r.usage),
                "results": f"comparison/{_folder(r.model)}/results.json",
                "report": f"comparison/{_folder(r.model)}/report.md",
            }
            for n, r in enumerate(results, 1)
        ],
    }


def markdown(comparison: dict[str, Any]) -> str:
    stamp, models = comparison["stamp"], comparison["models"]
    by_model = {m["model"]: m for m in models}
    best = by_model.get(comparison["recommended"] or "")
    recommendation = (
        f"- Cheapest model that passes the gate: **{best['model']}** "
        f"({report.usd(best['usage']['cost_per_answer_usd'], 5)} per answer, "
        f"{report.usd(best['usage']['cost_usd'], 4)} per run)"
        if best
        else "- No model passes the gate."
    )
    lines = [
        "# Model comparison",
        "",
        "> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM "
        "document. SGW, Bayport County and all data are fictional.",
        "",
        "Written by `make eval-compare`: the golden set against each model of the configured "
        "provider listed in `config/evals.yaml`, with the checks and gates of the "
        "[evaluation report](report.md); cost estimated at the prices in `config/llm.yaml`. "
        "Ranked: models that pass the gate, cheapest per answer first, then the others by "
        "pass rate.",
        "",
        recommendation,
        f"- Provider {stamp['provider']}, {stamp['cases']} cases, each {stamp['repeats']} "
        "time(s) per model",
        "- Prompts: " + ", ".join(f"{k} {v}" for k, v in stamp["prompt_versions"].items()),
        f"- Git commit: {stamp['git_commit']}",
        "",
        "## Pass rate per category",
        "",
        "| Rank | Model | Gate | " + " | ".join(report.TITLES[c] for c in CATEGORIES) + " | All |",
        "| --- | --- | --- | " + " | ".join("---" for _ in CATEGORIES) + " | --- |",
    ]
    for m in models:
        rates = [
            f"{s['pass_rate']:.0%}" if s["runs"] else "n/a"
            for s in (m["summary"][c] for c in CATEGORIES)
        ]
        lines.append(
            f"| {m['rank']} | {m['model']} | {verdict(m['gate_passed'])} | "
            + " | ".join(rates)
            + f" | "
            f"{m['pass_rate']:.0%} |"
        )
    lines += [
        "",
        "## Latency, tokens and cost",
        "",
        "Latency per answer, retries included; tokens and cost per run (every answer of every "
        "case).",
        "",
        "| Rank | Model | Latency P50 (ms) | Latency P90 (ms) | Tokens in | Tokens out | "
        "Cost per answer | Cost per run |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in models:
        u = m["usage"]
        lines.append(
            f"| {m['rank']} | {m['model']} | {u['latency_p50_ms']} | {u['latency_p90_ms']} | "
            f"{u['tokens_in']} | {u['tokens_out']} | {report.usd(u['cost_per_answer_usd'], 5)} | "
            f"{report.usd(u['cost_usd'], 4)} |"
        )
    lines += ["", "## Each model's results", ""]
    lines += [f"- {m['model']}: [report]({m['report']}), [results]({m['results']})" for m in models]
    return "\n".join(lines) + "\n"


def write_comparison(results: Sequence[ModelResult], golden: GoldenSet, out: Path) -> None:
    for r in results:
        write(r.evaluation, out / "comparison" / _folder(r.model))
    comparison = to_json(results, golden)
    (out / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    (out / "comparison.md").write_text(markdown(comparison))


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    providers: Providers | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT, help="where comparison.md goes")
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    parser.add_argument("--config", type=Path, default=EVAL_CONFIG)
    args = parser.parse_args(argv)

    settings = settings or get_settings()
    config = load_eval_config(args.config)
    if providers is None:
        try:
            providers = live_providers(settings, config.compare.models)
        except CompareError as error:
            print(f"eval-compare: {error}", file=sys.stderr)
            return 2
    golden = load_golden(args.golden)
    results = compare(golden, config, providers, settings)
    write_comparison(results, golden, args.out)
    for n, r in enumerate(results, 1):
        u = r.usage
        print(
            f"{n}. {r.model:<20} gate {verdict(r.evaluation.gate_passed)}, "
            f"{r.pass_rate:.0%} passed, P50 {u.latency_p50_ms} ms, P90 {u.latency_p90_ms} ms, "
            f"{report.usd(u.cost_per_answer_usd, 5)} per answer, "
            f"{report.usd(u.cost_usd, 4)} per run"
        )
    print(f"eval-compare: comparison in {args.out / 'comparison.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
