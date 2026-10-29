"""Activation levels (P-2.1 to P-2.5). A level is declared by a person, never computed: the
`propose_at_hours` thresholds in playbook_rules.yaml only drive the P-2.5 proposal.

The proposed level is the highest level whose threshold has been reached: at 72 h to landfall
`prepare` is proposed, at 48 h `full`. Before the first threshold nothing is proposed.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

FULL_ACTIVATION = "full"
PROPOSAL_RULE = "P-2.5"  # proposes a change of level; only a declaration closes it

DeclaringRole = Literal["director", "incident_commander"]
# P-2.5: the EOC Director declares Level 3 and Level 2, the Incident Commander Level 1.
DECLARED_BY: dict[str, DeclaringRole] = {
    "monitor": "director",
    "prepare": "director",
    FULL_ACTIVATION: "incident_commander",
}
LEVEL_NUMBER = {"monitor": 3, "prepare": 2, FULL_ACTIVATION: 1}


@dataclass(frozen=True)
class ActivationLevel:
    name: str
    propose_at_hours: float


def load_activation_levels(rules_path: Path) -> list[ActivationLevel]:
    rules = yaml.safe_load(rules_path.read_text())
    return [
        ActivationLevel(name=name, propose_at_hours=b["propose_at_hours"])
        for name, b in rules["activation_levels"].items()
    ]


def proposed_level(hours_to_landfall: float, levels: list[ActivationLevel]) -> str | None:
    """The level the thresholds propose at this time, or None before the first threshold."""
    reached = [lvl for lvl in levels if hours_to_landfall <= lvl.propose_at_hours]
    return min(reached, key=lambda lvl: lvl.propose_at_hours).name if reached else None
