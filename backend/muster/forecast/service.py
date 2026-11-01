"""The outage forecast per advisory and district (ticket 38): stored when the advisory is issued,
read with the field demand of the open playbook actions and what is available beside it.

Available is counted the way the ICS-215 counts it: crews per staging area still usable at the
advisory (not asked to leave under P-4.6), portable generators from the fuelled fleet
(`generators_fuelled`), which serves the whole territory. The forecast is context for the
EOC: it never becomes an ICS-215 row, a finding or operational state."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from sqlmodel import Session, col, delete, select

from muster import advisory_context
from muster.forecast.model import ForecastAsset, Spread, forecast
from muster.models import (
    Advisory,
    Asset,
    District,
    Finding,
    OpState,
    OutageForecast,
    PackageItem,
    StagingArea,
)
from muster.network import Network
from muster.planning.ics215 import usable_staging_areas
from muster.playbook.package import FIELD_WORK_KEYS, actionable, satisfying_state
from muster.playbook.service import Playbook
from muster.risk.model import AssetFeatures
from muster.risk.score import RuleBasedModel
from muster.scoring_config import FieldNeed, ForecastConfig, PlanningConfig


def district_names(session: Session) -> list[str]:
    """The districts west to east."""
    return list(session.exec(select(District.name).order_by(col(District.west_km))))


def store(
    session: Session,
    advisory: Advisory,
    assets: Sequence[AssetFeatures],
    rules: RuleBasedModel,
    network: Network,
    config: ForecastConfig,
) -> None:
    """Forecasts the advisory's customers out and field demand per district from the rule-based
    curves in use, and stores it. Seeded with `seed + advisory_no`: the same advisory forecasts
    the same figures every time."""
    forecast_assets = [ForecastAsset.of(a) for a in assets]
    member_p = rules.member_p_fail(assets)
    result = forecast(
        forecast_assets,
        network.fed_by,
        member_p,
        district_names(session),
        config,
        config.seed + advisory.advisory_no,
    )
    session.add_all(
        OutageForecast(
            advisory_no=advisory.advisory_no,
            district=d.district,
            model_version=rules.version,
            samples=member_p.shape[0] * config.draws,
            power_customers_p50=d.power_customers.p50,
            power_customers_p90=d.power_customers.p90,
            water_customers_p50=d.water_customers.p50,
            water_customers_p90=d.water_customers.p90,
            crews_p50=d.crews.p50,
            crews_p90=d.crews.p90,
            generators_p50=d.generators.p50,
            generators_p90=d.generators.p90,
            failed_assets_p50=d.failed_assets.p50,
            failed_assets_p90=d.failed_assets.p90,
        )
        for d in result
    )


def clear(session: Session) -> None:
    """Deletes every stored forecast (scenario reset)."""
    session.exec(delete(OutageForecast))


@dataclass(frozen=True)
class DistrictDemand:
    district: str
    power_customers: Spread
    water_customers: Spread
    failed_assets: Spread
    crews_needed: Spread  # for the expected failures plus the open actions
    generators_needed: Spread
    crews_for_actions: int  # the open playbook actions' share of the need
    generators_for_actions: int
    crews_available: int  # at the district's usable staging areas
    crews_short_p90: int  # crews the P90 needs beyond those available; 0 when there are enough


@dataclass(frozen=True)
class AdvisoryForecast:
    advisory_no: int
    model_version: int
    samples: int
    generators_available: int  # the fuelled fleet, for the whole territory
    districts: list[DistrictDemand]


def advisory_forecast(
    session: Session, advisory_no: int, playbook: Playbook, planning: PlanningConfig
) -> AdvisoryForecast:
    """The stored forecast of an issued advisory with the open actions' demand and what is
    available, district by district, west to east."""
    advisory = advisory_context.require_issued(session, advisory_no)
    rows = {
        r.district: r
        for r in session.exec(
            select(OutageForecast).where(OutageForecast.advisory_no == advisory_no)
        )
    }
    names = [n for n in district_names(session) if n in rows]
    actions = _action_demand(session, advisory, playbook, planning)
    crews_per_area = sum(r.per_staging_area or 0 for r in planning.resources.values() if r.is_crew)
    areas = [a.district for a in usable_staging_areas(session, advisory)]
    fuelled = session.get(OpState, ("event", "generators_fuelled"))
    first = next(iter(rows.values()), None)

    def shifted(spread: Spread, by: int) -> Spread:
        return replace(spread, p50=spread.p50 + by, p90=spread.p90 + by)

    districts = []
    for name in names:
        row = rows[name]
        need = actions.get(name, FieldNeed(crews=0, generators=0))
        crews, generators = need.crews, need.generators
        crews_needed = shifted(Spread(row.crews_p50, row.crews_p90), crews)
        available = crews_per_area * areas.count(name)
        districts.append(
            DistrictDemand(
                district=name,
                power_customers=Spread(row.power_customers_p50, row.power_customers_p90),
                water_customers=Spread(row.water_customers_p50, row.water_customers_p90),
                failed_assets=Spread(row.failed_assets_p50, row.failed_assets_p90),
                crews_needed=crews_needed,
                generators_needed=shifted(
                    Spread(row.generators_p50, row.generators_p90), generators
                ),
                crews_for_actions=crews,
                generators_for_actions=generators,
                crews_available=available,
                crews_short_p90=max(0, round(crews_needed.p90) - available),
            )
        )
    return AdvisoryForecast(
        advisory_no=advisory_no,
        model_version=first.model_version if first else 0,
        samples=first.samples if first else 0,
        generators_available=int(fuelled.value or 0) if fuelled else 0,
        districts=districts,
    )


def _action_demand(
    session: Session, advisory: Advisory, playbook: Playbook, planning: PlanningConfig
) -> dict[str, FieldNeed]:
    """District -> the crews and generators the advisory's open actions with field work need, as
    the ICS-215 would count them per site. An overridden action needs nothing."""
    overridden = set(
        session.exec(
            select(PackageItem.finding_id).where(
                PackageItem.advisory_no == advisory.advisory_no,
                PackageItem.status == "overridden",
            )
        )
    )
    district_of = {a.id: a.district for a in session.exec(select(Asset))}
    district_of |= {s.id: s.district for s in session.exec(select(StagingArea))}
    findings = session.exec(select(Finding).where(Finding.advisory_no == advisory.advisory_no))
    demand: dict[str, FieldNeed] = {}
    for finding in findings:
        if not actionable(finding) or finding.id in overridden:
            continue
        district = district_of.get(finding.entity_id)
        for change in satisfying_state(playbook, finding):
            if district is None or change.entity != finding.entity_id:
                continue
            if change.key not in FIELD_WORK_KEYS:
                continue
            resource = planning.resources[change.key]
            need = demand.get(district, FieldNeed(crews=0, generators=0))
            demand[district] = FieldNeed(
                crews=need.crews + (resource.per_site if resource.is_crew else 0),
                generators=need.generators + (0 if resource.is_crew else resource.per_site),
            )
    return demand
