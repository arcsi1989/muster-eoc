"""What changed survives the decision package's JSON column (stored with `asdict`)."""

import json
from dataclasses import asdict

from app.replay.diff import AdvisoryChanges, LandfallShift, RankMove, changes_from_json


def test_changes_read_back_equal_to_what_was_stored() -> None:
    changes = AdvisoryChanges(
        advisory_no=3,
        previous_advisory_no=2,
        landfall_shift=LandfallShift(41.2, "east"),
        max_wind_change_mph=5.0,
        peak_surge_change_m=0.3,
        activation_level_from="prepare",
        activation_level_to="prepare",
        top10_entered=["SUB-12"],
        top10_left=["WTP-01"],
        rank_moves=[RankMove("PS-14", 30, 12)],
    )

    assert changes_from_json(json.loads(json.dumps(asdict(changes)))) == changes


def test_initial_changes_read_back() -> None:
    initial = AdvisoryChanges(advisory_no=1, activation_level_to="monitor")

    assert changes_from_json(json.loads(json.dumps(asdict(initial)))) == initial
