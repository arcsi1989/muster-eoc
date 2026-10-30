"""The latest evaluation as an audit event: every backend start begins a fresh database, so the
summary in docs/eval/results.json is recorded again at startup, and a scenario reset keeps it,
as it keeps model versions. The model and prompt versions in the log carry their evaluation."""

import json
from pathlib import Path

from sqlmodel import Session

from muster.audit.log import record
from muster.evals.golden import verdict

EVALUATION_EVENT = "evaluation_run"


def record_latest(session: Session, results_path: Path | None) -> None:
    """Records the summary of the evaluation at `results_path`, if there is one."""
    if results_path is None or not results_path.exists():
        return
    results = json.loads(results_path.read_text())
    stamp, summary = results["stamp"], results["summary"]
    rates = ", ".join(f"{c} {s['passed']}/{s['runs']}" for c, s in summary.items())
    record(
        session,
        "system",
        EVALUATION_EVENT,
        f"Evaluation ({stamp['mode']}, {stamp['model'] or stamp['provider']}, "
        f"commit {stamp['git_commit']}): gate {verdict(results['gate_passed'])}; {rates}",
        None,
        {"gate_passed": results["gate_passed"], "mode": stamp["mode"], "summary": summary},
        {
            "model": stamp["model"],
            "prompt_versions": stamp["prompt_versions"],
            "git_commit": stamp["git_commit"],
        },
    )
