"""Runs the golden set and gates it (CR-03 C1).

    uv run python -m muster.evals.run           # make eval: the template provider, deterministic
    uv run python -m muster.evals.run --live    # make eval-llm: the configured provider, repeated

Writes report.md and results.json (default docs/eval/), stamped with the model, the prompt
versions and the git commit, and exits non-zero when a category is below its threshold in
config/evals.yaml. The backend records the latest results as an audit event at startup."""

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from muster.agent.draft import sitrep_prompt
from muster.config import REPO_ROOT, Settings, get_settings
from muster.copilot.chat import copilot_prompt
from muster.evals import report
from muster.evals.checks import Verdict, check
from muster.evals.golden import (
    CATEGORIES,
    Case,
    Category,
    EvalConfig,
    GoldenSet,
    Step,
    load_eval_config,
    load_golden,
    verdict,
)
from muster.evals.scenario import Prompts, Transcript, world
from muster.llm.factory import build_provider
from muster.llm.provider import LLMProvider
from muster.llm.template import TemplateProvider
from muster.scoring_config import load_scoring_config

GOLDEN = REPO_ROOT / "backend" / "tests" / "evals" / "golden.yaml"
EVAL_CONFIG = REPO_ROOT / "config" / "evals.yaml"
OUT = REPO_ROOT / "docs" / "eval"


@dataclass(frozen=True)
class Run:
    verdict: Verdict
    transcript: Transcript

    @property
    def problems(self) -> list[str]:
        return self.verdict.problems

    @property
    def passed(self) -> bool:
        return not self.problems

    def to_json(self) -> dict[str, Any]:
        """A failed run keeps its whole transcript; a passed one what it answered and with what."""
        t = self.transcript
        transcript = (
            t.to_json()
            if self.problems
            else {
                "answer": t.answer,
                "tools_used": [c.name for c in t.tool_calls],
                "citations": t.citations,
                "provider": t.provider,
                "fallback": t.fallback,
                "model": t.model,
                "prompt_version": t.prompt_version,
            }
        )
        return {"passed": self.passed, "problems": self.problems, "transcript": transcript}


@dataclass(frozen=True)
class CaseResult:
    case: Case
    runs: list[Run]


@dataclass(frozen=True)
class CategorySummary:
    cases: int
    runs: int
    passed: int
    pass_rate: float
    failed_elsewhere: int  # runs of other categories that leaked or wrote (zero gates only)
    threshold: str
    gate_passed: bool


@dataclass(frozen=True)
class Stamp:
    mode: str  # template or live
    provider: str
    model: str | None
    prompt_versions: dict[str, str]
    git_commit: str
    repeats: int


@dataclass(frozen=True)
class Evaluation:
    stamp: Stamp
    results: list[CaseResult]
    summary: dict[Category, CategorySummary]

    @property
    def gate_passed(self) -> bool:
        return all(s.gate_passed for s in self.summary.values())

    def to_json(self) -> dict[str, Any]:
        return {
            "stamp": asdict(self.stamp),
            "gate_passed": self.gate_passed,
            "summary": {c: asdict(s) for c, s in self.summary.items()},
            "cases": [
                {
                    "id": r.case.id,
                    "category": r.case.category,
                    "advisory": r.case.advisory,
                    "question": r.case.question,
                    "runs": [run.to_json() for run in r.runs],
                }
                for r in self.results
            ],
        }


def run_cases(
    golden: GoldenSet,
    provider: LLMProvider,
    prompts: Prompts,
    repeats: int,
    settings: Settings,
    folder: Path,
) -> list[CaseResult]:
    """Every case `repeats` times. Cases with the same setup share one scenario, advanced in
    advisory order; a step at an advisory happens before the cases at it."""
    groups: dict[str, list[Case]] = {}
    for case in golden.cases:
        key = json.dumps([s.model_dump() for s in case.setup], sort_keys=True)
        groups.setdefault(key, []).append(case)
    results: dict[str, CaseResult] = {}
    for n, cases in enumerate(groups.values()):
        steps: list[Step] = cases[0].setup
        timeline: list[tuple[int, int, Step | Case]] = [(s.at, 0, s) for s in steps]
        timeline += [(c.advisory, 1, c) for c in cases]
        with world(folder / f"scenario-{n}", settings) as scenario:
            for at, _, event in sorted(timeline, key=lambda e: (e[0], e[1])):
                if isinstance(event, Step):
                    scenario.apply(event)
                    continue
                scenario.issue_until(at)
                runs = []
                for _ in range(repeats):
                    transcript = scenario.run(event, provider, prompts)
                    runs.append(Run(check(transcript, event.expect), transcript))
                results[event.id] = CaseResult(event, runs)
    return [results[c.id] for c in golden.cases]


def _elsewhere(category: Category, runs: list[Run]) -> int:
    """Runs of other categories that count against `category`'s gate: a leak against
    classification, a write attempt or state change against injection, wherever it happened."""
    if category == "classification":
        return sum(run.verdict.leaked for run in runs)
    if category == "injection":
        return sum(run.verdict.wrote for run in runs)
    return 0


def summarise(results: list[CaseResult], config: EvalConfig) -> dict[Category, CategorySummary]:
    summary = {}
    for category in CATEGORIES:
        cases = [r for r in results if r.case.category == category]
        runs = [run for r in cases for run in r.runs]
        others = [run for r in results if r.case.category != category for run in r.runs]
        passed = sum(run.passed for run in runs)
        elsewhere = _elsewhere(category, others)
        gate = config.gates[category]
        threshold = (
            f"at most {gate.max_failures} failed"
            if gate.max_failures is not None
            else f"pass rate at least {gate.min_pass_rate:.0%}"
        )
        summary[category] = CategorySummary(
            cases=len(cases),
            runs=len(runs),
            passed=passed,
            pass_rate=passed / len(runs) if runs else 0.0,
            failed_elsewhere=elsewhere,
            threshold=threshold,
            gate_passed=gate.passes(passed, len(runs), elsewhere),
        )
    return summary


def git_commit() -> str:
    """The commit evaluated, marked +dirty when the working tree has changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return head + ("+dirty" if dirty else "")


def evaluate(
    golden: GoldenSet,
    config: EvalConfig,
    provider: LLMProvider,
    settings: Settings,
    live: bool,
    prompts: Prompts | None = None,
) -> Evaluation:
    """Runs the suite with `provider` (`prompts` replaces the shipped prompts) and summarises it
    against the gates."""
    scoring = load_scoring_config(settings.scoring_config_path)
    prompts = prompts or Prompts(copilot_prompt(scoring.copilot), sitrep_prompt(scoring.draft))
    repeats = config.repeats.live if live else config.repeats.template
    with tempfile.TemporaryDirectory(prefix="sgw-eval-") as folder:
        results = run_cases(golden, provider, prompts, repeats, settings, Path(folder))
    stamp = Stamp(
        mode="live" if live else "template",
        provider=provider.name,
        model=provider.model,
        prompt_versions={"copilot": prompts.copilot.version, "sitrep": prompts.sitrep.version},
        git_commit=git_commit(),
        repeats=repeats,
    )
    return Evaluation(stamp, results, summarise(results, config))


def write(evaluation: Evaluation, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(evaluation.to_json(), indent=2) + "\n")
    (out / "report.md").write_text(report.markdown(evaluation.to_json()))


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="use the configured LLM provider")
    parser.add_argument("--out", type=Path, default=OUT, help="where report.md goes")
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    parser.add_argument("--config", type=Path, default=EVAL_CONFIG)
    args = parser.parse_args(argv)

    settings = settings or get_settings()
    scoring = load_scoring_config(settings.scoring_config_path)
    provider = (
        build_provider(settings, scoring) if args.live else TemplateProvider.from_config(scoring)
    )
    evaluation = evaluate(
        load_golden(args.golden), load_eval_config(args.config), provider, settings, args.live
    )
    write(evaluation, args.out)
    for category, s in evaluation.summary.items():
        elsewhere = f", {s.failed_elsewhere} elsewhere" if s.failed_elsewhere else ""
        print(
            f"{category:<15} {s.passed}/{s.runs}{elsewhere} ({s.pass_rate:.0%}; {s.threshold}): "
            + ("ok" if s.gate_passed else "FAILED")
        )
    print(f"eval: gate {verdict(evaluation.gate_passed)}; report in {args.out}")
    return 0 if evaluation.gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
