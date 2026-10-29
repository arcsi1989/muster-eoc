"""Builds the evaluation context for an advisory (plan section 2.4) and stores the findings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, delete, select

from app import advisory_context
from app.models import Advisory, Exposure, Finding, OpState, Score, StagingArea
from app.network import load_network
from app.playbook.activation import ActivationLevel, load_activation_levels
from app.playbook.clauses import Clause, parse_clauses
from app.playbook.engine import Entity, Status, evaluate
from app.playbook.engine import Finding as EngineFinding
from app.playbook.retrieval import ClauseIndex
from app.playbook.rules import Rulebook, load_rulebook

# The definition of event.critical_feeding_assets_top25 (P-4.3, plan section 2.4): top-25 risk
# assets that feed a hospital or the treatment plant. Part of the field's name, not a tunable.
CRITICAL_TYPES = {"hospital", "treatment_plant"}
CRITICAL_TOP_N = 25


@dataclass(frozen=True)
class Playbook:
    rulebook: Rulebook
    levels: list[ActivationLevel]
    clauses: list[Clause]
    index: ClauseIndex


def load_playbook(rules_path: Path, playbook_path: Path) -> Playbook:
    clauses = parse_clauses(playbook_path)
    return Playbook(
        rulebook=load_rulebook(rules_path),
        levels=load_activation_levels(rules_path),
        clauses=clauses,
        index=ClauseIndex.build(clauses),
    )


def _state(session: Session) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in session.exec(select(OpState)):
        state.setdefault(row.entity, {})[row.key] = row.value
    return state


def evaluation_context(
    session: Session, advisory: Advisory, playbook: Playbook
) -> tuple[dict[str, Any], list[Entity]]:
    """The event fields and one entity per asset and staging area, for the rule engine."""
    network = load_network(session)
    state = _state(session)
    scores = {
        s.asset_id: s
        for s in session.exec(select(Score).where(Score.advisory_no == advisory.advisory_no))
    }
    exposures = {
        e.site_id: e
        for e in session.exec(select(Exposure).where(Exposure.advisory_no == advisory.advisory_no))
    }
    context = advisory_context.at(session, playbook.levels, advisory)
    feeds_types = {a: network.feeds_facility_types(a) for a in network.assets}

    event_state = state.get("event", {})
    event = {
        "hours_to_landfall": advisory.hours_to_landfall,
        "activation_level": context.activation_level,
        "hours_since_full_activation": context.hours_since_full_activation,
        "regulator_notified": event_state.get("regulator_notified", False),
        "generators_fuelled": event_state.get("generators_fuelled", 0),
        "critical_feeding_assets_top25": sum(
            1
            for a, s in scores.items()
            if s.rank <= CRITICAL_TOP_N and feeds_types[a] & CRITICAL_TYPES
        ),
        **{flag: event_state.get(flag, False) for flag in advisory_context.PER_ADVISORY_FLAGS},
    }

    def exposure_values(site_id: str) -> dict[str, Any]:
        e = exposures.get(site_id)
        if e is None:
            return {}
        return {
            "wind_p50_mph": e.wind_p50_mph,
            "wind_p90_mph": e.wind_p90_mph,
            "flood_depth_p50_m": e.flood_depth_p50_m,
            "flood_depth_p90_m": e.flood_depth_p90_m,
            "tsforce_arrival_h": e.tsforce_arrival_h,
        }

    entities = []
    for asset in network.assets.values():
        score = scores.get(asset.id)
        fed = [f.id for f in network.direct_facilities(asset.id)]
        fed += network.treatment_plants_reached(asset.id)
        entities.append(
            Entity(
                asset.id,
                "asset",
                {
                    "asset": {
                        "id": asset.id,
                        "type": asset.type,
                        "condition_score": asset.condition_score,
                        "distance_to_coast_km": asset.distance_to_coast_km,
                        "feeds_facility_types": sorted(feeds_types[asset.id]),
                        "feeds_facility_ids": fed,
                        "risk_rank": score.rank if score else None,
                        "p_fail": score.p_fail if score else None,
                    },
                    "exposure": exposure_values(asset.id),
                    "state": state.get(asset.id, {}),
                },
            )
        )
    for site_id, e in exposures.items():
        if e.site_kind == "staging_area":
            entities.append(
                Entity(
                    site_id,
                    "staging_area",
                    {
                        "staging": {"id": site_id, "flood_depth_p90_m": e.flood_depth_p90_m},
                        "state": state.get(site_id, {}),
                    },
                )
            )
    return event, entities


def store_findings(session: Session, advisory: Advisory, playbook: Playbook) -> list[EngineFinding]:
    event, entities = evaluation_context(session, advisory, playbook)
    findings = evaluate(playbook.rulebook, event, entities)
    session.add_all(
        Finding(
            advisory_no=advisory.advisory_no,
            rule_id=f.rule_id,
            entity_id=f.entity_id,
            entity_kind=f.entity_kind,
            status=f.status,
            severity=f.severity,
            owner_role=f.owner_role,
            cites=f.cites,
            overdue=f.overdue,
            details=f.details,
        )
        for f in findings
    )
    return findings


def clear_findings(session: Session) -> None:
    """Deletes every stored finding (scenario reset)."""
    session.exec(delete(Finding))


def findings(session: Session, advisory_no: int, status: Status | None = None) -> list[Finding]:
    query = select(Finding).where(Finding.advisory_no == advisory_no)
    if status:
        query = query.where(Finding.status == status)
    return list(session.exec(query.order_by(col(Finding.id))))


@dataclass(frozen=True)
class FindingView:
    """A stored finding with what a reader needs: the rule's title and the entity's name."""

    finding: Finding
    title: str
    entity_name: str | None


def finding_views(
    session: Session, playbook: Playbook, advisory_no: int, status: Status | None = None
) -> list[FindingView]:
    titles = {r.id: r.title for r in playbook.rulebook.rules}
    network = load_network(session)
    staging = {s.id: s.name for s in session.exec(select(StagingArea))}

    def name(entity_id: str) -> str | None:
        described = network.describe(entity_id)
        return described[1] if described else staging.get(entity_id)

    return [
        FindingView(f, titles[f.rule_id], name(f.entity_id))
        for f in findings(session, advisory_no, status)
    ]


def refresh_event_finding(
    session: Session, advisory: Advisory, playbook: Playbook, rule_id: str
) -> Finding | None:
    """Re-evaluates one event-level rule after a state change made outside the package (the
    situation report approval for P-7.1) and updates its stored finding."""
    rule = next(r for r in playbook.rulebook.rules if r.id == rule_id)
    event, _ = evaluation_context(session, advisory, playbook)
    single = playbook.rulebook.model_copy(update={"rules": [rule]})
    results = evaluate(single, event, [])
    stored = session.exec(
        select(Finding).where(
            Finding.advisory_no == advisory.advisory_no,
            Finding.rule_id == rule_id,
            Finding.entity_id == "event",
        )
    ).first()
    if stored is None or not results:
        return stored
    stored.status = results[0].status
    stored.details = results[0].details
    session.add(stored)
    return stored
