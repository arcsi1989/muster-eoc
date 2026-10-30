"""The ICS-215 operational planning worksheet (CR-02 C3): one row per approved field task, with
the resource it needs. Deterministic: rows come from the playbook's field work, never from a
model.

"Have" is drawn from the stock the operational state and the staging data show, in approval
order: portable generators from the fuelled fleet (`generators_fuelled`), crews from the staging
areas still usable at the advisory (not forecast to flood, not vacated). "Need" is required
minus have."""

import math

from sqlmodel import Session, col, select

from app.models import Advisory, Asset, Exposure, OpState, StagingArea
from app.planning.products import Ics215Row
from app.playbook.package import field_work
from app.playbook.service import Playbook, entity_names
from app.scoring_config import PlanningConfig, PlanningResource


def usable_staging_areas(session: Session, advisory: Advisory) -> list[StagingArea]:
    """The staging areas crews can work from at `advisory`: not forecast to flood (P-4.6) and
    not vacated."""
    flooded = {
        e.site_id
        for e in session.exec(
            select(Exposure).where(
                Exposure.advisory_no == advisory.advisory_no, Exposure.flood_depth_p90_m > 0
            )
        )
    }
    vacated = {
        s.entity
        for s in session.exec(select(OpState).where(OpState.key == "relocated"))
        if s.value is True
    }
    areas = session.exec(select(StagingArea).order_by(col(StagingArea.id))).all()
    return [a for a in areas if a.id not in flooded | vacated]


def worksheet(
    session: Session, advisory: Advisory, playbook: Playbook, config: PlanningConfig
) -> list[Ics215Row]:
    """The ICS-215 for the operational period after `advisory`: the approved field tasks of the
    packages up to and including its own, oldest approval first."""
    names = entity_names(session)
    bases = usable_staging_areas(session, advisory)
    positions = {a.id: (a.x_km, a.y_km) for a in session.exec(select(Asset))}
    positions |= {s.id: (s.x_km, s.y_km) for s in session.exec(select(StagingArea))}
    event_state = {
        s.key: s.value for s in session.exec(select(OpState).where(OpState.entity == "event"))
    }
    stock: dict[str, int] = {}

    def stock_of(resource: PlanningResource) -> int:
        if resource.stock_state is not None:
            return int(event_state.get(resource.stock_state) or 0)
        return (resource.per_staging_area or 0) * len(bases)

    rows = []
    for work in field_work(session, advisory, playbook):
        item = work.item
        for change in work.completes:
            resource = config.resources[change.key]
            available = stock.setdefault(resource.kind, stock_of(resource))
            have = min(resource.per_site, available)
            stock[resource.kind] = available - have
            base = _nearest(positions.get(item.entity_id), bases, exclude=item.entity_id)
            rows.append(
                Ics215Row(
                    item_id=item.id or 0,
                    clause_id=item.rule_id,
                    location_id=item.entity_id,
                    location=names.get(item.entity_id, item.entity_id),
                    work_assignment=item.proposed_action,
                    resource_kind=resource.kind,
                    required=resource.per_site,
                    have=have,
                    need=resource.per_site - have,
                    reporting_location_id=base.id if base else None,
                    reporting_location=base.name if base else None,
                    requested_arrival_hours=advisory.hours_to_landfall - config.period_hours,
                    stop_work=work.stop_work,
                )
            )
    return rows


def _nearest(
    site: tuple[float, float] | None, bases: list[StagingArea], exclude: str
) -> StagingArea | None:
    """The usable staging area closest to the site; a staging area being vacated reports to
    another one."""
    candidates = [b for b in bases if b.id != exclude]
    if site is None or not candidates:
        return None
    return min(candidates, key=lambda b: (math.dist(site, (b.x_km, b.y_km)), b.id))
