"""Activation level derived from hours to landfall, using the bounds in playbook_rules.yaml.

A boundary hour belongs to the later, higher level: (to_hours, from_hours]. The lowest level
also covers landfall and after (docs/decisions.md).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

FULL_ACTIVATION = "full"


@dataclass(frozen=True)
class ActivationLevel:
    name: str
    from_hours: float
    to_hours: float


def load_activation_levels(rules_path: Path) -> list[ActivationLevel]:
    rules = yaml.safe_load(rules_path.read_text())
    return [
        ActivationLevel(name=name, from_hours=b["from_hours"], to_hours=b["to_hours"])
        for name, b in rules["activation_levels"].items()
    ]


def activation_level(hours_to_landfall: float, levels: list[ActivationLevel]) -> str | None:
    """The level in force, or None before the first level starts."""
    for level in levels:
        if level.to_hours < hours_to_landfall <= level.from_hours:
            return level.name
    last = min(levels, key=lambda lvl: lvl.to_hours)
    return last.name if hours_to_landfall <= last.to_hours else None
