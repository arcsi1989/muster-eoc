"""The synthetic storm history (CR-03 C2): past fictional storms over today's asset base, with
varied tracks and intensities, and outcomes drawn from the hidden truth (app/datagen/truth.py).
The challenger model trains on it; Storm Delta stays out as the held-out test storm.

    uv run python -m app.datagen.history      (make history; make data runs it too)
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.config import REPO_ROOT, get_settings
from app.datagen.generate import (
    SCENARIO_START,
    TRUE_CURVES,
    straight_track,
    write_json,
)
from app.datagen.truth import HiddenTruth, simulate_failures
from app.ingest.contracts import SyntheticStormFile
from app.models_config import HistoryConfig, load_models_config
from app.scoring_config import ScoringConfig, load_scoring_config

# Training data for the challenger, not app data: outside data/gold, which the app loads.
HISTORY_FILE = REPO_ROOT / "data" / "history" / "synthetic_storms.json"


def build_history(
    assets: list[dict[str, Any]],
    coastline: dict[str, Any],
    history: HistoryConfig,
    scoring: ScoringConfig,
) -> list[dict[str, Any]]:
    """`history.storms` past storms, reproducible from `history.seed`. Every storm meets today's
    asset base: ages and condition scores are those of the scenario date."""
    rng = np.random.default_rng(history.seed)
    storms = []
    for i in range(history.storms):

        def draw(bounds: tuple[float, float]) -> float:
            return round(float(rng.uniform(*bounds)), 1)

        landfall_x, heading = draw(history.landfall_x_km), draw(history.heading_deg_from_east)
        vmax, surge, rmax = (
            draw(history.vmax_mph),
            draw(history.peak_surge_m),
            draw(history.rmax_km),
        )
        year = int(rng.integers(history.year_range[0], history.year_range[1] + 1))
        # A label only (ages count to the scenario date): some day of the season's peak.
        landfall_at = datetime(year, 8, 1, 18, tzinfo=UTC) + timedelta(
            days=int(rng.integers(0, 70))
        )
        track, landfall = straight_track(
            landfall_x, heading, vmax, rmax, history.hours_before_landfall
        )
        storm: dict[str, Any] = {
            "name": f"Storm S{i + 1:02d}",
            "landfall_at": landfall_at.isoformat(),
            "landfall_t_hours": float(history.hours_before_landfall),
            "track": track,
            "landfall": landfall,
            "peak_surge_m": surge,
        }
        storm["outcomes"] = simulate_failures(
            storm,
            assets,
            coastline,
            HiddenTruth(TRUE_CURVES, history.age_condition_effect, SCENARIO_START.year),
            scoring,
            rng,
        )
        storms.append(SyntheticStormFile.model_validate(storm).model_dump(mode="json"))
    return storms


def generate_history(
    gold_dir: Path, out_file: Path, history: HistoryConfig, scoring: ScoringConfig
) -> None:
    """Writes the history, simulated over the gold assets and coastline."""
    assets = json.loads((gold_dir / "assets.json").read_text())
    coastline = json.loads((gold_dir / "coastline.geojson").read_text())
    write_json(out_file, build_history(assets, coastline, history, scoring))


if __name__ == "__main__":
    settings = get_settings()
    generate_history(
        settings.data_dir,
        HISTORY_FILE,
        load_models_config(settings.models_config_path).history,
        load_scoring_config(settings.scoring_config_path),
    )
    print(f"Synthetic history written: {HISTORY_FILE.relative_to(REPO_ROOT)}")
