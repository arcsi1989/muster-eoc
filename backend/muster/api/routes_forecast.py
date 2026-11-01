from dataclasses import asdict

from fastapi import APIRouter

from muster.api.routes_risk import AdvisoryQuery
from muster.api.schemas import ForecastOut
from muster.deps import PlaybookDep, ScoringConfigDep, SessionDep
from muster.forecast.service import advisory_forecast

router = APIRouter()


@router.get("/forecast", response_model=ForecastOut)
def get_forecast(
    session: SessionDep, playbook: PlaybookDep, config: ScoringConfigDep, advisory: AdvisoryQuery
) -> ForecastOut:
    """Customers out (power and water) and crews and generators needed against available, per
    district, as median and P90 over the advisory's ensemble."""
    return ForecastOut.model_validate(
        asdict(advisory_forecast(session, advisory, playbook, config.planning))
    )
