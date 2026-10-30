"""The challenger's way from shadow to champion (CR-03 C2). It is registered as a model version
in shadow; it is proposed only when it passes the promotion rule on the held-out storm; a person
approves it through the model-version path (app.calibration.versions). Never automatic."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from app import advisory_context
from app.audit.log import record
from app.calibration import versions
from app.calibration.backtest import BacktestMetrics
from app.challenger.model import ChallengerModel, Comparison, TrainedChallenger
from app.errors import ConflictError
from app.models import Advisory, ModelVersion
from app.models_config import PromotionRule

PROPOSED_EVENT = "challenger_proposed"


class NotPromotable(ConflictError):
    code = "not_promotable"


class AlreadyProposed(ConflictError):
    code = "already_proposed"


@dataclass(frozen=True)
class Criterion:
    name: str
    value: float  # the challenger's margin, or its calibration error
    threshold: float
    passed: bool


@dataclass(frozen=True)
class PromotionCheck:
    storm: str
    criteria: list[Criterion]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.criteria)


def calibration_error(metrics: BacktestMetrics) -> float:
    """Mean |predicted - observed| over the reliability bins, weighted by assets per bin."""
    filled = [b for b in metrics.reliability if b.count]
    gaps = sum(b.count * abs((b.mean_predicted or 0.0) - (b.observed_rate or 0.0)) for b in filled)
    return gaps / sum(b.count for b in filled)


def check(storm: str, held_out: Comparison, rule: PromotionRule) -> PromotionCheck:
    challenger, champion = held_out.challenger, held_out.champion
    brier_gain = champion.brier - challenger.brier
    capture_gain = challenger.top_capture - champion.top_capture
    error = calibration_error(challenger)
    return PromotionCheck(
        storm,
        [
            _at_least("brier_improvement", brier_gain, rule.min_brier_improvement),
            _at_least("top_capture_gain", capture_gain, rule.min_top_capture_gain),
            Criterion(
                "calibration_error",
                error,
                rule.max_calibration_error,
                error <= rule.max_calibration_error,
            ),
        ],
    )


def _at_least(name: str, value: float, threshold: float) -> Criterion:
    return Criterion(name, value, threshold, value >= threshold)


def register(session: Session, trained: TrainedChallenger) -> ChallengerModel:
    """The challenger's model version, created in shadow the first time it is seen."""
    version = session.exec(
        select(ModelVersion).where(
            ModelVersion.kind == "challenger", ModelVersion.label == trained.name
        )
    ).first()
    if version is None:
        version = ModelVersion(
            label=trained.name,
            kind="challenger",
            status="shadow",
            curves=[],
            created_at=datetime.now(UTC),
            backtest={"storm": trained.held_out_storm, **asdict(trained.held_out)},
        )
        session.add(version)
        session.commit()
        session.refresh(version)
    return ChallengerModel(version.id or 0, trained)


def propose(session: Session, challenger: ChallengerModel, rule: PromotionRule) -> ModelVersion:
    """Proposes the challenger for approval if it passes the rule; refuses otherwise. Proposing
    changes no ranking: only a person's approval does."""
    version = versions.get(session, challenger.version)
    if version.status != "shadow":
        raise AlreadyProposed(f"model version {version.id} is already {version.status}")
    trained = challenger.trained
    result = check(trained.held_out_storm, trained.held_out, rule)
    if not result.passed:
        failed = ", ".join(c.name for c in result.criteria if not c.passed)
        raise NotPromotable(
            f"the challenger does not pass the promotion rule on {result.storm}: {failed}"
        )
    version.status = "proposed"
    session.add(version)
    current = advisory_context.current_advisory_no(session)
    record(
        session,
        "system",
        PROPOSED_EVENT,
        f"Challenger {version.label} passed the promotion rule on {result.storm}; model "
        f"version {version.id} proposed, awaiting approval",
        session.get(Advisory, current) if current else None,
        {"model_version": version.id, "criteria": [asdict(c) for c in result.criteria]},
        {"model_version": version.id},
    )
    session.commit()
    session.refresh(version)
    return version
