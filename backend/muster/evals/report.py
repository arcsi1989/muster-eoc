"""docs/eval/report.md from an evaluation's results: the stamp, a table per category, and each
failed run with its transcript."""

import json
from typing import Any

from muster.evals.golden import verdict

TITLES = {  # one per golden.Category
    "grounding": "Grounding and citations",
    "refusal": "Correct refusal",
    "classification": "Data classification",
    "injection": "Prompt injection",
    "drafting": "Drafting",
}


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _failure(case: dict[str, Any], number: int, run: dict[str, Any]) -> list[str]:
    t = run["transcript"]
    lines = [
        f"### {case['id']}, run {number}",
        "",
        *[f"- {p}" for p in run["problems"]],
        "",
        f"Provider {t['provider']}{' (fallback)' if t['fallback'] else ''}, "
        f"model {t['model'] or 'none'}, prompt {t['prompt_version'] or 'none'}.",
        "",
    ]
    if t["question"]:
        lines += [f"**Question:** {t['question']}", ""]
    lines += ["**Answer:**", "", "```text", t["answer"], "```", ""]
    calls = json.dumps(t["tool_calls"], indent=2, default=str)
    lines += [
        "<details><summary>Tool calls and what the model was shown</summary>",
        "",
        "```json",
        calls,
        "```",
        "",
        "</details>",
        "",
    ]
    return lines


def markdown(results: dict[str, Any]) -> str:
    stamp, summary = results["stamp"], results["summary"]
    lines = [
        "# Evaluation report",
        "",
        "> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM "
        "document. SGW, Bayport County and all data are fictional.",
        "",
        "Written by `make eval` (template provider) or `make eval-llm` (the configured provider); "
        "checks are rules only, thresholds in `config/evals.yaml` (CR-03 C1).",
        "",
        f"- Gate: **{verdict(results['gate_passed'])}**",
        f"- Mode: {stamp['mode']}, provider {stamp['provider']}, "
        f"model {stamp['model'] or 'none'}, each case {stamp['repeats']} time(s)",
        "- Prompts: " + ", ".join(f"{k} {v}" for k, v in stamp["prompt_versions"].items()),
        f"- Git commit: {stamp['git_commit']}",
        "",
        "| Category | Cases | Runs | Passed | Pass rate | Failed elsewhere | Threshold | Gate |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for category, s in summary.items():
        lines.append(
            f"| {TITLES[category]} | {s['cases']} | {s['runs']} | {s['passed']} | "
            f"{s['pass_rate']:.0%} | {s['failed_elsewhere']} | {s['threshold']} | "
            f"{'ok' if s['gate_passed'] else 'FAILED'} |"
        )
    for category in summary:
        lines += [
            "",
            f"## {TITLES[category]}",
            "",
            "| Case | Advisory | Question or task | Passed runs |",
            "| --- | --- | --- | --- |",
        ]
        for case in results["cases"]:
            if case["category"] == category:
                passed = sum(r["passed"] for r in case["runs"])
                task = (
                    case["question"] or f"Draft the situation report at advisory {case['advisory']}"
                )
                lines.append(
                    f"| {case['id']} | {case['advisory']} | {_cell(task)} | "
                    f"{passed}/{len(case['runs'])} |"
                )
    failures = [
        _failure(case, n, run)
        for case in results["cases"]
        for n, run in enumerate(case["runs"], 1)
        if not run["passed"]
    ]
    lines += ["", "## Failures", ""]
    lines += [line for f in failures for line in f] if failures else ["None.", ""]
    return "\n".join(lines).rstrip() + "\n"
