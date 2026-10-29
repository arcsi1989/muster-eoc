from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.agent import cycle as advisory_cycle
from app.api.schemas import (
    AdvisoryOut,
    ChangesOut,
    PointOut,
    ScenarioOut,
    TimelineSlotOut,
    TrackPointOut,
)
from app.deps import CycleDep, SessionDep, SettingsDep, get_activation_levels, get_scoring_config
from app.hazard.track import cone_polygon
from app.playbook.activation import ActivationLevel, activation_level
from app.replay import service
from app.scoring_config import ScoringConfig

router = APIRouter(prefix="/advisories")

LevelsDep = Annotated[list[ActivationLevel], Depends(get_activation_levels)]
ConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]


def _scenario(session: Session, levels: list[ActivationLevel]) -> ScenarioOut:
    advisories = service.all_advisories(session)
    current = service.current_advisory(session)
    issued = [a for a in advisories if a.advisory_no <= current]
    return ScenarioOut(
        total_advisories=len(advisories),
        current_advisory=current,
        timeline=[
            TimelineSlotOut(
                advisory_no=a.advisory_no,
                hours_to_landfall=a.hours_to_landfall,
                activation_level=activation_level(a.hours_to_landfall, levels),
                issued=a.advisory_no <= current,
            )
            for a in advisories
        ],
        advisories=[
            AdvisoryOut(
                advisory_no=a.advisory_no,
                issued_at=a.issued_at,
                hours_to_landfall=a.hours_to_landfall,
                activation_level=activation_level(a.hours_to_landfall, levels),
                max_wind_mph=service.max_wind_mph(a),
                peak_surge_m=a.peak_surge_m,
                landfall=PointOut(x_km=a.landfall_x_km, y_km=a.landfall_y_km),
                track=[TrackPointOut.model_validate(p) for p in a.track],
                cone=[PointOut(x_km=x, y_km=y) for x, y in cone_polygon(a.track, a.cone_radius_km)],
            )
            for a in issued
        ],
    )


@router.get("", response_model=ScenarioOut)
def get_scenario(session: SessionDep, levels: LevelsDep) -> ScenarioOut:
    return _scenario(session, levels)


@router.post("/next", response_model=ScenarioOut)
def next_advisory(
    session: SessionDep, levels: LevelsDep, config: ConfigDep, cycle: CycleDep
) -> ScenarioOut:
    advisory_cycle.issue_next_advisory(session, config, cycle)
    return _scenario(session, levels)


@router.post("/reset", response_model=ScenarioOut)
def reset_scenario(
    session: SessionDep, levels: LevelsDep, cycle: CycleDep, settings: SettingsDep
) -> ScenarioOut:
    advisory_cycle.reset_scenario(session, cycle, settings.data_dir)
    return _scenario(session, levels)


@router.get("/{advisory_no}/changes", response_model=ChangesOut)
def get_changes(advisory_no: int, session: SessionDep, levels: LevelsDep) -> ChangesOut:
    return ChangesOut.model_validate(asdict(service.changes(session, advisory_no, levels)))
