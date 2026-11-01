"""Committed results files (docs/eval/): a dataclass report as JSON, every float to six decimals
so the file stays readable and stable in diffs. Both back-tests (the challenger's and the outage
forecast's) write through it."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def rounded(value: Any) -> Any:
    """Every float at any depth to six decimals."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value


def as_results(report: Any) -> Any:
    """A dataclass report as the plain, rounded data its results file holds."""
    return rounded(asdict(report))


def write_results(report: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_results(report), indent=2) + "\n")
