"""Numbers in model prose and whether a tool result holds them: the one number rule, used by the
copilot's runtime validator and by the evaluation's grounding and classification checks, so the
two cannot drift (decisions.md, tickets 35 and 39)."""

import json
import re
from collections.abc import Sequence
from typing import Any, NamedTuple

# A number in prose, also glued to its unit (40km, 12h); not part of an ID (SUB-07, P-4.2, T-48)
# or a name (P90).
NUMBER = re.compile(r"(?<![\w.\-])\d[\d,]*(?:\.\d+)?")
# Ordinals that name percentiles (90th percentile, 90th-percentile, the 50th and 90th
# percentiles): a name, like P90.
_ORDINAL = r"\d+(?:st|nd|rd|th)"
PERCENTILE = re.compile(
    rf"\b{_ORDINAL}(?:(?:,\s*|\s+)(?:and\s+|or\s+)?{_ORDINAL})*[\s\-\u2013]+percentiles?\b", re.I
)
# Slack for binary floats when a written number is compared at exactly half a unit.
FLOAT_TOLERANCE = 1e-9


class WrittenNumber(NamedTuple):
    raw: str  # as written (4,400)
    value: float
    decimals: int  # written after the point


def shown_text(results: Sequence[Any]) -> str:
    """A turn's tool results, as the model was shown them, as one text: what grounds an answer's
    IDs and numbers."""
    return json.dumps(list(results), default=str)


def numbers_in(text: str) -> list[WrittenNumber]:
    """Each number in `text`; percentile names (90th percentile) are not numbers."""
    found = []
    for raw in NUMBER.findall(PERCENTILE.sub(" ", text)):
        plain = raw.rstrip(",").replace(",", "")
        decimals = len(plain.split(".")[1]) if "." in plain else 0
        found.append(WrittenNumber(raw.rstrip(","), float(plain), decimals))
    return found


def within_half_unit(value: float, written: float, decimals: int) -> bool:
    """`written` is within half a unit of its last decimal of `value`. At exactly half a unit
    either neighbour passes (0.565 as 0.56 or 0.57), so half-up rounding counts whatever the
    binary float (Python's round(0.565, 2) gives 0.56)."""
    return abs(value - written) <= 0.5 * 10.0**-decimals + FLOAT_TOLERANCE


def _rounds_to(value: float, written: float, decimals: int) -> bool:
    """`written` is `value` rounded to `decimals` places, or a probability (a value in [0, 1])
    written as a percentage."""
    forms = (value, value * 100) if 0 <= value <= 1 else (value,)
    return any(within_half_unit(v, written, decimals) for v in forms)


def ungrounded_numbers(answer: str, results: Sequence[Any]) -> list[str]:
    """Numbers in `answer`, as written and each once, that none of the turn's tool `results`
    holds, as written or rounded (a probability may be written as a percentage)."""
    shown = [n.value for n in numbers_in(shown_text(results))]
    ungrounded = (
        n.raw
        for n in numbers_in(answer)
        if not any(_rounds_to(v, n.value, n.decimals) for v in shown)
    )
    return list(dict.fromkeys(ungrounded))


def rounded(value: Any) -> Any:
    """Every float at any depth to six decimals: a committed results file stays readable and
    stable in diffs."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value
