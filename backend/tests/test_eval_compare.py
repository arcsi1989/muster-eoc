"""Tokens, latency and cost per answer in the evaluation, and the model comparison
(`make eval-compare`). Fake providers of different quality, speed and token use stand in for the
models: no network."""

import json
from dataclasses import replace
from itertools import cycle
from pathlib import Path
from typing import Any

import pytest

from muster.config import Settings
from muster.evals import compare
from muster.evals.golden import EvalConfig, GoldenSet, Repeats, load_eval_config, load_golden
from muster.evals.run import EVAL_CONFIG, GOLDEN, evaluate
from muster.evals.usage import AnswerUsage, answer_usage, percentile, run_usage
from muster.ids import CLAUSE_ID, ENTITY_ID
from muster.llm.config import load_llm_config
from muster.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    ObjectivesRequest,
    ObjectivesResult,
    Prompt,
    ToolRunner,
)
from muster.llm.template import TemplateProvider
from muster.llm.template_chat import template_chat
from muster.scoring_config import load_scoring_config
from tests import conftest

# One setup-free case per category with a pass-rate gate: the zero-failure gates pass empty.
CASES = ("grounding-why-ps14", "refusal-dispatch", "drafting-advisory-2")
LATENCIES = (100, 200, 300, 400, 500, 600)  # ms, one per call, in turn


class Fake:
    """A model that answers like the template and reports its own tokens and latency. A sloppy
    one leaves the IDs out, so it fails grounding but passes validation (no retry)."""

    name = "fake"

    def __init__(
        self, settings: Settings, model: str, tokens: tuple[int, int], slower: int, sloppy: bool
    ) -> None:
        self.model: str | None = model
        self._template = TemplateProvider.from_config(
            load_scoring_config(settings.scoring_config_path)
        )
        self._usage = {"input_tokens": tokens[0], "output_tokens": tokens[1]}
        self._latency = cycle([ms * slower for ms in LATENCIES])
        self._sloppy = sloppy

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult:
        result = template_chat(question, run_tool, 5)
        text = result.text
        if self._sloppy:
            text = CLAUSE_ID.sub("the clause", ENTITY_ID.sub("the site", text))
        latency = next(self._latency)
        return ChatResult(text, result.tools_used, self.model, prompt.version, latency, self._usage)

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        result = self._template.draft_sitrep(request, prompt)
        latency = next(self._latency)
        return replace(
            result,
            provider=self.name,
            model=self.model,
            prompt_version=prompt.version,
            latency_ms=latency,
            usage=self._usage,
        )

    def rephrase_objectives(self, request: ObjectivesRequest, prompt: Prompt) -> ObjectivesResult:
        return self._template.rephrase_objectives(request, prompt)


def golden() -> GoldenSet:
    return GoldenSet(cases=[c for c in load_golden(GOLDEN).cases if c.id in CASES])


def config(models: list[str]) -> EvalConfig:
    loaded = load_eval_config(EVAL_CONFIG)
    return loaded.model_copy(
        update={
            "repeats": Repeats(template=1, live=2),
            "compare": loaded.compare.model_copy(update={"models": models}),
        }
    )


def fakes(settings: Settings) -> dict[str, Fake]:
    return {
        # good, slow, the most tokens
        "claude-opus-5-5": Fake(settings, "claude-opus-5-5", (1000, 200), 3, sloppy=False),
        # good, medium
        "claude-sonnet-5-5": Fake(settings, "claude-sonnet-5-5", (800, 100), 2, sloppy=False),
        # sloppy, fast, the fewest tokens
        "claude-haiku-5-5": Fake(settings, "claude-haiku-5-5", (600, 50), 1, sloppy=True),
    }


def test_percentiles_are_nearest_rank() -> None:
    assert percentile([300, 100, 200, 600, 500, 400], 0.5) == 300
    assert percentile([300, 100, 200, 600, 500, 400], 0.9) == 600
    assert percentile([7], 0.9) == 7
    assert percentile([], 0.5) == 0


def test_an_answer_costs_each_attempt_at_its_model_price() -> None:
    llm = load_llm_config(conftest.test_settings(Path()).llm_config_path)
    attempts = [
        {
            "model": "claude-sonnet-5-5",
            "latency_ms": 900,
            "usage": {"input_tokens": 1000, "output_tokens": 100},
        },
        {
            "model": "claude-opus-5-5",
            "latency_ms": 1100,
            "usage": {"input_tokens": 1000, "output_tokens": 100},
        },
    ]

    usage = answer_usage(attempts, llm)

    assert (usage.latency_ms, usage.tokens_in, usage.tokens_out) == (2000, 2000, 200)
    assert usage.cost_usd == pytest.approx((2000 + 1000 + 4000 + 2000) / 1e6)
    assert answer_usage([], llm) == AnswerUsage(0, 0, 0, 0.0), "the template: no call, no cost"
    unpriced = [{"model": "x", "latency_ms": 5, "usage": {"input_tokens": 1, "output_tokens": 1}}]
    assert answer_usage(unpriced, llm).cost_usd is None
    assert answer_usage(unpriced + attempts, llm).cost_usd is None


def test_a_run_sums_tokens_and_cost_and_an_unpriced_answer_leaves_the_cost_unknown() -> None:
    answers = [
        AnswerUsage(100, 10, 1, 0.5),
        AnswerUsage(300, 20, 2, 1.5),
        AnswerUsage(200, 0, 0, 0.0),
    ]

    usage = run_usage(answers)

    assert (usage.answers, usage.tokens_in, usage.tokens_out) == (3, 30, 3)
    assert usage.cost_usd == pytest.approx(2.0)
    assert usage.cost_per_answer_usd == pytest.approx(2.0 / 3)
    assert (usage.latency_p50_ms, usage.latency_p90_ms) == (200, 300)
    unknown = run_usage([*answers, AnswerUsage(1, 1, 1, None)])
    assert unknown.cost_usd is None and unknown.cost_per_answer_usd is None


def test_results_json_records_tokens_latency_and_cost_per_answer_and_per_run(
    tmp_path: Path,
) -> None:
    settings = conftest.test_settings(tmp_path)
    model = fakes(settings)["claude-sonnet-5-5"]

    results = evaluate(golden(), config([]), model, settings, live=True).to_json()

    runs = [run for case in results["cases"] for run in case["runs"]]
    assert len(runs) == 6
    per_answer = (800 * 2.00 + 100 * 10.00) / 1e6
    for run in runs:
        assert run["usage"]["tokens_in"] == 800 and run["usage"]["tokens_out"] == 100
        assert run["usage"]["cost_usd"] == pytest.approx(per_answer)
    assert sorted(run["usage"]["latency_ms"] for run in runs) == [ms * 2 for ms in LATENCIES]
    usage = results["usage"]
    assert (usage["answers"], usage["tokens_in"], usage["tokens_out"]) == (6, 4800, 600)
    assert usage["cost_usd"] == pytest.approx(6 * per_answer)
    assert (usage["latency_p50_ms"], usage["latency_p90_ms"]) == (600, 1200)


def test_the_template_run_costs_nothing(tmp_path: Path) -> None:
    settings = conftest.test_settings(tmp_path)
    template = TemplateProvider.from_config(load_scoring_config(settings.scoring_config_path))

    usage = evaluate(golden(), config([]), template, settings, live=False).to_json()["usage"]

    assert usage == {
        "answers": 3,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "cost_per_answer_usd": 0.0,
        "latency_p50_ms": 0,
        "latency_p90_ms": 0,
    }


def test_the_comparison_ranks_passing_models_cheapest_first_and_sums_each(tmp_path: Path) -> None:
    settings = conftest.test_settings(tmp_path)
    models = fakes(settings)
    order = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]

    comparison = compare.compare(golden(), config(order), models.__getitem__, settings)

    assert [m.model for m in comparison] == [
        "claude-sonnet-5-5",  # passes, cheaper than Opus
        "claude-opus-5-5",  # passes
        "claude-haiku-5-5",  # the cheapest, but fails grounding
    ]
    sonnet, opus, haiku = comparison
    assert sonnet.evaluation.gate_passed and opus.evaluation.gate_passed
    assert not haiku.evaluation.gate_passed
    assert haiku.evaluation.summary["grounding"].pass_rate == 0.0
    assert haiku.evaluation.summary["refusal"].pass_rate == 1.0
    assert (opus.usage.tokens_in, opus.usage.tokens_out) == (6000, 1200)
    assert opus.usage.cost_per_answer_usd == pytest.approx((1000 * 4 + 200 * 20) / 1e6)
    assert opus.usage.cost_usd == pytest.approx(6 * (1000 * 4 + 200 * 20) / 1e6)
    assert haiku.usage.cost_usd == pytest.approx(6 * (600 * 0.10 + 50 * 0.50) / 1e6)
    assert (opus.usage.latency_p50_ms, opus.usage.latency_p90_ms) == (900, 1800)
    assert (haiku.usage.latency_p50_ms, haiku.usage.latency_p90_ms) == (300, 600)


def test_an_unpriced_model_ranks_after_priced_ones_that_pass(tmp_path: Path) -> None:
    settings = conftest.test_settings(tmp_path)
    models = {
        "unpriced": Fake(settings, "unpriced", (10, 10), 1, sloppy=False),
        "claude-opus-5-5": Fake(settings, "claude-opus-5-5", (1000, 200), 1, sloppy=False),
    }

    comparison = compare.compare(golden(), config(list(models)), models.__getitem__, settings)

    assert [m.model for m in comparison] == ["claude-opus-5-5", "unpriced"]
    assert comparison[1].usage.cost_usd is None


def test_make_eval_compare_writes_the_table_and_each_model_report(tmp_path: Path) -> None:
    settings = conftest.test_settings(tmp_path)
    models = fakes(settings)
    golden_path = tmp_path / "golden.yaml"
    golden_path.write_text(json.dumps(golden().model_dump(mode="json", exclude_defaults=True)))
    config_path = tmp_path / "evals.yaml"
    cfg = config(["claude-opus-5-5", "claude-haiku-5-5", "claude-sonnet-5-5"])
    config_path.write_text(json.dumps(cfg.model_dump(mode="json")))
    out = tmp_path / "eval"

    code = compare.main(
        ["--golden", str(golden_path), "--config", str(config_path), "--out", str(out)],
        settings,
        models.__getitem__,
    )

    assert code == 0
    table = (out / "comparison.md").read_text()
    assert "Cheapest model that passes the gate: **claude-sonnet-5-5**" in table
    assert "| 1 | claude-sonnet-5-5 | passed | 100% | 100% | n/a | n/a | 100% | 100% |" in table
    assert "| 3 | claude-haiku-5-5 | FAILED | 0% | 100% | n/a | n/a | 100% | 67% |" in table
    assert "| 2 | claude-opus-5-5 | 900 | 1800 | 6000 | 1200 | $0.00800 | $0.0480 |" in table
    data = json.loads((out / "comparison.json").read_text())
    assert [m["model"] for m in data["models"]] == [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-haiku-5-5",
    ]
    assert data["models"][0]["usage"]["tokens_in"] == 4800
    per_model = json.loads((out / "comparison" / "claude-haiku-5-5" / "results.json").read_text())
    assert per_model["stamp"]["model"] == "claude-haiku-5-5" and not per_model["gate_passed"]
    assert (out / "comparison" / "claude-haiku-5-5" / "report.md").exists()


def test_the_template_provider_has_no_models_to_compare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = conftest.test_settings(tmp_path)  # LLM_PROVIDER=template

    assert compare.main(["--out", str(tmp_path / "eval")], settings) == 2
    assert "LLM_PROVIDER" in capsys.readouterr().err
    assert not (tmp_path / "eval").exists()
