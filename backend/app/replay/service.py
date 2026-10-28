"""Replays the advisories one at a time and scores each one as it is issued."""

from sqlmodel import Session, col, delete, select

from app.errors import ConflictError, DataNotLoaded, NotFound
from app.hazard.service import store_exposure
from app.models import Advisory, Asset, Exposure, ScenarioState, Score
from app.playbook.activation import ActivationLevel, activation_level
from app.replay.diff import AdvisoryChanges, AdvisorySnapshot, diff
from app.risk.score import placeholder_score
from app.scoring_config import ScoringConfig


class ScenarioComplete(ConflictError):
    code = "scenario_complete"


def _state(session: Session) -> ScenarioState:
    state = session.get(ScenarioState, 1)
    if state is None:
        raise DataNotLoaded("scenario state missing; the gold data was not loaded")
    return state


def issued_advisories(session: Session) -> list[Advisory]:
    current = _state(session).current_advisory
    query = (
        select(Advisory).where(Advisory.advisory_no <= current).order_by(col(Advisory.advisory_no))
    )
    return list(session.exec(query))


def all_advisories(session: Session) -> list[Advisory]:
    return list(session.exec(select(Advisory).order_by(col(Advisory.advisory_no))))


def current_advisory(session: Session) -> int:
    return _state(session).current_advisory


def max_wind_mph(advisory: Advisory) -> float:
    return max(float(point["vmax_mph"]) for point in advisory.track)


def advance(session: Session, config: ScoringConfig) -> None:
    """Issues the next advisory: computes hazard exposure, then scores every asset."""
    state = _state(session)
    advisory = session.get(Advisory, state.current_advisory + 1)
    if advisory is None:
        raise ScenarioComplete(f"all {state.current_advisory} advisories have been issued")
    store_exposure(session, advisory, config.hazard)

    assets = session.exec(select(Asset)).all()
    scored = sorted(
        (
            (
                placeholder_score(a.x_km, a.y_km, advisory.landfall_x_km, advisory.landfall_y_km),
                a.id,
            )
            for a in assets
        ),
        key=lambda pair: (-pair[0], pair[1]),
    )
    session.add_all(
        Score(asset_id=asset_id, advisory_no=advisory.advisory_no, score=score, rank=rank)
        for rank, (score, asset_id) in enumerate(scored, start=1)
    )
    state.current_advisory = advisory.advisory_no
    session.add(state)
    session.commit()


def reset(session: Session) -> None:
    """Returns to before advisory 1."""
    session.exec(delete(Score))
    session.exec(delete(Exposure))
    state = _state(session)
    state.current_advisory = 0
    session.add(state)
    session.commit()


def _require_issued(session: Session, advisory_no: int) -> Advisory:
    advisory = session.get(Advisory, advisory_no)
    if advisory is None or advisory_no > _state(session).current_advisory:
        raise NotFound(f"advisory {advisory_no} has not been issued")
    return advisory


def ranked_scores(session: Session, advisory_no: int) -> list[Score]:
    _require_issued(session, advisory_no)
    query = select(Score).where(Score.advisory_no == advisory_no).order_by(col(Score.rank))
    return list(session.exec(query))


def ranks(session: Session, advisory_no: int) -> dict[str, int]:
    """Rank per asset at an advisory; empty when it has not been issued."""
    query = select(Score).where(Score.advisory_no == advisory_no)
    return {s.asset_id: s.rank for s in session.exec(query)}


def changes(session: Session, advisory_no: int, levels: list[ActivationLevel]) -> AdvisoryChanges:
    """What changed at an issued advisory compared with the one before."""

    def snapshot(advisory: Advisory) -> AdvisorySnapshot:
        return AdvisorySnapshot(
            advisory_no=advisory.advisory_no,
            landfall_x_km=advisory.landfall_x_km,
            landfall_y_km=advisory.landfall_y_km,
            max_wind_mph=max_wind_mph(advisory),
            peak_surge_m=advisory.peak_surge_m,
            activation_level=activation_level(advisory.hours_to_landfall, levels),
            ranks=ranks(session, advisory.advisory_no),
        )

    current = _require_issued(session, advisory_no)
    previous = session.get(Advisory, advisory_no - 1)
    return diff(snapshot(current), snapshot(previous) if previous else None)


def exposures(session: Session, advisory_no: int) -> list[Exposure]:
    _require_issued(session, advisory_no)
    query = (
        select(Exposure).where(Exposure.advisory_no == advisory_no).order_by(col(Exposure.site_id))
    )
    return list(session.exec(query))
