"""Replays the advisories one at a time and scores each one as it is issued."""

from pathlib import Path

from sqlmodel import Session, col, delete, select

from app import advisory_context
from app.calibration import versions
from app.errors import ConflictError, DataNotLoaded, NotFound
from app.hazard.service import store_exposure
from app.ingest.loader import restore_initial_state
from app.models import (
    Advisory,
    Alert,
    Exposure,
    ScenarioState,
    Score,
    StagingArea,
)
from app.network import load_network
from app.playbook.activation import ActivationLevel
from app.replay.diff import AdvisoryChanges, AdvisorySnapshot, diff
from app.risk.alerts import RankedRisk, raise_alerts
from app.risk.score import score_assets
from app.scoring_config import ScoringConfig


class ScenarioComplete(ConflictError):
    code = "scenario_complete"


def _state(session: Session) -> ScenarioState:
    state = session.get(ScenarioState, 1)
    if state is None:
        raise DataNotLoaded("scenario state missing; the gold data was not loaded")
    return state


def issued_advisories(session: Session) -> list[Advisory]:
    current = advisory_context.current_advisory_no(session)
    query = (
        select(Advisory).where(Advisory.advisory_no <= current).order_by(col(Advisory.advisory_no))
    )
    return list(session.exec(query))


def all_advisories(session: Session) -> list[Advisory]:
    return list(session.exec(select(Advisory).order_by(col(Advisory.advisory_no))))


def total_advisories(session: Session) -> int:
    return len(session.exec(select(Advisory.advisory_no)).all())


def max_wind_mph(advisory: Advisory) -> float:
    return max(float(point["vmax_mph"]) for point in advisory.track)


def advance(session: Session, config: ScoringConfig) -> Advisory:
    """Issues the next advisory: computes hazard exposure, scores and ranks every asset with the
    model version in use (the latest approved), and raises alerts against the previous advisory.
    The caller commits, so that what else starts the new advisory lands in the same transaction.
    The advisory cycle (agent) evaluates the playbook next."""
    state = _state(session)
    advisory = session.get(Advisory, state.current_advisory + 1)
    if advisory is None:
        raise ScenarioComplete(f"all {state.current_advisory} advisories have been issued")

    exposures = store_exposure(session, advisory, config.hazard)
    model_version = versions.in_use(session)
    scores = score_assets(
        [e for e in exposures if e.kind == "asset"],
        load_network(session),
        model_version.curves,
        config,
        advisory.issued_at.date(),
    )
    ranked = list(enumerate(sorted(scores, key=lambda s: (-s.risk, s.asset_id)), start=1))
    session.add_all(
        Score(
            asset_id=s.asset_id,
            advisory_no=advisory.advisory_no,
            model_version=model_version.id,
            p_wind=s.p_wind,
            p_flood=s.p_flood,
            p_fail=s.p_fail,
            consequence=s.consequence.total,
            risk=s.risk,
            rank=rank,
            confidence=s.confidence,
            confidence_reasons=s.confidence_reasons,
            factors=s.factors(),
        )
        for rank, s in ranked
    )

    previous = {
        s.asset_id: RankedRisk(s.asset_id, s.risk, s.rank)
        for s in session.exec(select(Score).where(Score.advisory_no == advisory.advisory_no - 1))
    }
    current = [RankedRisk(s.asset_id, s.risk, rank) for rank, s in ranked]
    session.add_all(
        Alert(advisory_no=advisory.advisory_no, asset_id=a.asset_id, kind=a.kind, message=a.message)
        for a in raise_alerts(current, previous, config.risk.alert, config.risk.top_n)
    )
    state.current_advisory = advisory.advisory_no
    session.add(state)
    session.flush()
    return advisory


def reset(session: Session, data_dir: Path) -> None:
    """Returns the replay to before advisory 1: no advisory, no scores, the initial operational
    state. The modules that own decisions, findings and the audit log clear their own tables."""
    session.exec(delete(Alert))
    session.exec(delete(Score))
    session.exec(delete(Exposure))
    restore_initial_state(session, data_dir)
    state = _state(session)
    state.current_advisory = 0
    session.add(state)
    session.commit()


def require_issued(session: Session, advisory_no: int) -> Advisory:
    advisory = session.get(Advisory, advisory_no)
    if advisory is None or advisory_no > advisory_context.current_advisory_no(session):
        raise NotFound(f"advisory {advisory_no} has not been issued")
    return advisory


def ranked_scores(session: Session, advisory_no: int) -> list[Score]:
    require_issued(session, advisory_no)
    query = select(Score).where(Score.advisory_no == advisory_no).order_by(col(Score.rank))
    return list(session.exec(query))


def model_version(session: Session, advisory_no: int) -> int | None:
    """The model version that scored an advisory; None before it is issued."""
    return session.exec(select(Score.model_version).where(Score.advisory_no == advisory_no)).first()


def ranks(session: Session, advisory_no: int) -> dict[str, int]:
    """Rank per asset at an advisory; empty when it has not been issued."""
    query = select(Score).where(Score.advisory_no == advisory_no)
    return {s.asset_id: s.rank for s in session.exec(query)}


def changes(
    session: Session, advisory_no: int, levels: list[ActivationLevel], top_n: int
) -> AdvisoryChanges:
    """What changed at an issued advisory compared with the one before."""

    def snapshot(advisory: Advisory) -> AdvisorySnapshot:
        return AdvisorySnapshot(
            advisory_no=advisory.advisory_no,
            landfall_x_km=advisory.landfall_x_km,
            landfall_y_km=advisory.landfall_y_km,
            max_wind_mph=max_wind_mph(advisory),
            peak_surge_m=advisory.peak_surge_m,
            activation_level=advisory_context.at(session, levels, advisory).activation_level,
            ranks=ranks(session, advisory.advisory_no),
        )

    current = require_issued(session, advisory_no)
    previous = session.get(Advisory, advisory_no - 1)
    return diff(snapshot(current), snapshot(previous) if previous else None, top_n)


def exposures(session: Session, advisory_no: int) -> list[Exposure]:
    require_issued(session, advisory_no)
    query = (
        select(Exposure).where(Exposure.advisory_no == advisory_no).order_by(col(Exposure.site_id))
    )
    return list(session.exec(query))


def score(session: Session, asset_id: str, advisory_no: int) -> Score:
    require_issued(session, advisory_no)
    found = session.get(Score, (asset_id, advisory_no))
    if found is None:
        raise NotFound(f"asset {asset_id} was not scored")
    return found


def exposure(session: Session, site_id: str, advisory_no: int) -> Exposure | None:
    return session.get(Exposure, (site_id, advisory_no))


def alerts(session: Session, advisory_no: int) -> list[Alert]:
    require_issued(session, advisory_no)
    query = select(Alert).where(Alert.advisory_no == advisory_no).order_by(col(Alert.id))
    return list(session.exec(query))


def staging_area_name(session: Session, area_id: str) -> str | None:
    area = session.get(StagingArea, area_id)
    return area.name if area else None
