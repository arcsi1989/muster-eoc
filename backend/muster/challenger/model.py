"""The trained challenger as a risk model. `make train` saves it with its held-out comparison;
the backend loads it at startup and scores every advisory with it in shadow."""

import logging
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV

from muster.calibration.backtest import BacktestMetrics
from muster.challenger.dataset import ASSET_TYPES, FEATURES, feature_matrix
from muster.geo import FloatArray
from muster.risk.model import AssetFeatures, Prediction

logger = logging.getLogger(__name__)

TYPE_COLUMN = FEATURES.index("asset_type")


@dataclass(frozen=True)
class ModelMetrics(BacktestMetrics):
    roc_auc: float | None  # None when every row has the same outcome


@dataclass(frozen=True)
class Comparison:
    challenger: ModelMetrics
    champion: ModelMetrics


@dataclass(frozen=True)
class TrainedChallenger:
    """What `make train` saves: the final model, the baseline its explanations compare with and
    how it did against the champion on the held-out storm (a `Comparison`)."""

    name: str  # e.g. challenger-hgb-20storms-seed42
    model: CalibratedClassifierCV
    baseline: list[float]  # per feature: the training median (the most common asset type)
    held_out_storm: str
    held_out: Comparison


def baseline(features: FloatArray) -> list[float]:
    medians = [float(v) for v in np.median(features, axis=0)]
    codes, counts = np.unique(features[:, TYPE_COLUMN], return_counts=True)
    medians[TYPE_COLUMN] = float(codes[int(np.argmax(counts))])
    return medians


def save(trained: TrainedChallenger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(trained))


def load(path: Path) -> TrainedChallenger | None:
    """The saved challenger; None (logged) if there is none, so the app runs without shadow
    scoring. The file is the one `make train` wrote in this repo, never user input."""
    if not path.exists():
        logger.warning("no challenger model at %s; run make train for shadow scoring", path)
        return None
    trained = pickle.loads(path.read_bytes())  # noqa: S301 (our own build artefact)
    if not isinstance(trained, TrainedChallenger):
        raise TypeError(f"{path} does not hold a trained challenger")
    return trained


class ChallengerModel:
    """The challenger behind the risk model interface. Its factors per asset are each feature's
    contribution: how much p_fail drops when that feature alone is set to the baseline."""

    def __init__(self, version: int, trained: TrainedChallenger) -> None:
        self._version = version
        self.trained = trained

    @property
    def version(self) -> int:
        return self._version

    def _p(self, rows: FloatArray) -> FloatArray:
        p: FloatArray = self.trained.model.predict_proba(rows)[:, 1]
        return p

    def predict(self, assets: Sequence[AssetFeatures]) -> list[Prediction]:
        if not assets:
            return []
        rows = feature_matrix(assets)
        # One call for the rows and, per feature, the rows with that feature at the baseline:
        # each scikit-learn call has a fixed cost, so eleven small calls would cost eleven.
        moved = np.repeat(rows[np.newaxis], len(self.trained.baseline), axis=0)
        for column, value in enumerate(self.trained.baseline):
            moved[column, :, column] = value
        all_p = self._p(np.vstack([rows, *moved]))
        p = all_p[: len(rows)]
        contribution = (p - all_p[len(rows) :].reshape(len(moved), len(rows))).T
        return [
            Prediction(
                asset_id=a.asset.id,
                p_fail=float(p[i]),
                factors={"features": _ranked(rows[i], contribution[i])},
                version=self._version,
            )
            for i, a in enumerate(assets)
        ]


def _ranked(row: FloatArray, contribution: FloatArray) -> list[dict[str, Any]]:
    """Every feature with its value and contribution, the largest push upward first."""
    features = [
        {
            "feature": name,
            "value": ASSET_TYPES[int(row[i])] if i == TYPE_COLUMN else float(row[i]),
            "contribution": float(contribution[i]),
        }
        for i, name in enumerate(FEATURES)
    ]
    return sorted(features, key=lambda f: (-f["contribution"], f["feature"]))
