from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from muster import advisory_context
from muster.agent import cycle as advisory_cycle
from muster.agent import lifecycle
from muster.api.schemas import (
    AdvisoryOut,
    PastPositionOut,
    PointOut,
    ScenarioOut,
    StormPositionOut,
    TimelineSlotOut,
    TrackPointOut,
)
from muster.deps import (
    ChallengerDep,
    CycleDep,
    SessionDep,
    SettingsDep,
    get_activation_levels,
    get_scoring_config,
)
from muster.hazard.track import cone_polygon, intensity_category
from muster.models import Advisory
from muster.playbook.activation import ActivationLevel
from muster.replay import service
from muster.replay.diff import AdvisoryChanges
from muster.scoring_config import ScoringConfig

router = APIRouter(prefix="/advisories")

LevelsDep = Annotated[list[ActivationLevel], Depends(get_activation_levels)]
ConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]


def _scenario(
    session: Session, levels: list[ActivationLevel], config: ScoringConfig
) -> ScenarioOut:
    advisories = service.all_advisories(session)
    current = advisory_context.current_advisory_no(session)
    issued = [a for a in advisories if a.advisory_no <= current]
    category_min_mph = config.hazard.intensity_min_mph

    def level(advisory: Advisory) -> str | None:
        return advisory_context.at(session, levels, advisory).activation_level

    def track_point(advisory: Advisory, point: dict[str, Any]) -> TrackPointOut:
        return TrackPointOut.model_validate(
            {
                **point,
                "valid_at": advisory.issued_at + timedelta(hours=point["t_hours"]),
                "category": intensity_category(point["vmax_mph"], category_min_mph),
            }
        )

    def past_position(advisory: Advisory) -> PastPositionOut:
        start = track_point(advisory, advisory.track[0])
        return PastPositionOut(
            advisory_no=advisory.advisory_no,
            **start.model_dump(include=set(StormPositionOut.model_fields)),
        )

    return ScenarioOut(
        total_advisories=len(advisories),
        current_advisory=current,
        timeline=[
            TimelineSlotOut(
                advisory_no=a.advisory_no,
                hours_to_landfall=a.hours_to_landfall,
                activation_level=level(a),
                issued=a.advisory_no <= current,
            )
            for a in advisories
        ],
        advisories=[
            AdvisoryOut(
                advisory_no=a.advisory_no,
                issued_at=a.issued_at,
                hours_to_landfall=a.hours_to_landfall,
                activation_level=level(a),
                max_wind_mph=service.max_wind_mph(a),
                peak_surge_m=a.peak_surge_m,
                landfall=PointOut(x_km=a.landfall_x_km, y_km=a.landfall_y_km),
                track=[track_point(a, p) for p in a.track],
                past_positions=[past_position(e) for e in issued if e.advisory_no < a.advisory_no],
                cone=[PointOut(x_km=x, y_km=y) for x, y in cone_polygon(a.track, a.cone_radius_km)],
            )
            for a in issued
        ],
    )


@router.get("", response_model=ScenarioOut)
def get_scenario(session: SessionDep, levels: LevelsDep, config: ConfigDep) -> ScenarioOut:
    return _scenario(session, levels, config)


@router.post("/next", response_model=ScenarioOut)
def next_advisory(
    session: SessionDep,
    levels: LevelsDep,
    config: ConfigDep,
    cycle: CycleDep,
    challenger: ChallengerDep,
) -> ScenarioOut:
    lifecycle.issue_next_advisory(session, config, cycle, challenger)
    return _scenario(session, levels, config)


@router.post("/reset", response_model=ScenarioOut)
def reset_scenario(
    session: SessionDep,
    levels: LevelsDep,
    config: ConfigDep,
    cycle: CycleDep,
    settings: SettingsDep,
) -> ScenarioOut:
    advisory_cycle.reset_scenario(session, cycle, settings.data_dir)
    return _scenario(session, levels, config)


@router.get("/{advisory_no}/changes", response_model=AdvisoryChanges)
def get_changes(
    advisory_no: int, session: SessionDep, levels: LevelsDep, config: ConfigDep
) -> AdvisoryChanges:
    return service.changes(session, advisory_no, levels, config.risk.top_n)
