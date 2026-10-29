"""The advisory cycle as a LangGraph StateGraph (plan section 4, ADR 0001).

load_context -> diff -> evaluate_rules -> draft -> await_approval <-> apply_decision -> finalise

Only `apply_decision` changes operational state, and it is deterministic: the LLM never writes
state, never decides whether a rule is met and never changes scores. Every node writes an audit
event. The graph state holds only the advisory number and the decision being applied; the
package, its items and the findings live in the database.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.agent import decisions
from app.agent.actions import proposed_action
from app.agent.draft import PROMPT_VERSION, template_draft
from app.audit.log import record
from app.errors import AppError, DataNotLoaded
from app.models import Advisory, DecisionPackage, Finding, OpState, PackageItem, Score
from app.network import load_network
from app.playbook.activation import activation_level
from app.playbook.service import Playbook, store_findings
from app.replay import service

SITREP_RULE = "P-7.1"  # satisfied only by approving the situation report, never an item
MODEL_VERSION = "published-curves"


class CycleState(TypedDict, total=False):
    advisory_no: int
    decision: dict[str, Any]


def build_graph(engine: Engine, playbook: Playbook) -> StateGraph[CycleState]:
    versions = {
        "rules_version": playbook.rulebook.version,
        "model_version": MODEL_VERSION,
        "prompt_version": PROMPT_VERSION,
    }
    rules = {r.id: r for r in playbook.rulebook.rules}

    @contextmanager
    def unit() -> Iterator[Session]:
        with Session(engine) as session:
            yield session
            session.commit()

    def advisory_of(session: Session, state: CycleState) -> Advisory:
        advisory = session.get(Advisory, state["advisory_no"])
        if advisory is None:
            raise DataNotLoaded(f"advisory {state['advisory_no']} missing")
        return advisory

    def load_context(state: CycleState) -> CycleState:
        with unit() as session:
            advisory = advisory_of(session, state)
            top10 = session.exec(
                select(Score.asset_id)
                .where(Score.advisory_no == advisory.advisory_no, Score.rank <= 10)
                .order_by(col(Score.rank))
            ).all()
            event_state = {
                s.key: s.value
                for s in session.exec(select(OpState).where(OpState.entity == "event"))
            }
            level = activation_level(advisory.hours_to_landfall, playbook.levels)
            record(
                session,
                "system",
                "context_loaded",
                f"Advisory {advisory.advisory_no} loaded: "
                f"{advisory.hours_to_landfall} h to landfall, {level}",
                advisory,
                {"top10": list(top10), "event_state": event_state, "activation_level": level},
                versions,
            )
        return {}

    def diff(state: CycleState) -> CycleState:
        with unit() as session:
            advisory = advisory_of(session, state)
            changes = asdict(service.changes(session, advisory.advisory_no, playbook.levels))
            session.merge(
                DecisionPackage(
                    advisory_no=advisory.advisory_no,
                    status="open",
                    changes=changes,
                    draft={},
                    opened_at=datetime.now(UTC),
                )
            )
            moves = len(changes["rank_moves"])
            record(
                session,
                "system",
                "diff",
                f"Compared with advisory {changes['previous_advisory_no'] or '-'}: "
                f"{moves} rank moves",
                advisory,
                changes,
                versions,
            )
        return {}

    def evaluate_rules(state: CycleState) -> CycleState:
        with unit() as session:
            advisory = advisory_of(session, state)
            findings = store_findings(session, advisory, playbook)
            session.flush()
            network = load_network(session)
            stored = session.exec(
                select(Finding).where(Finding.advisory_no == advisory.advisory_no)
            ).all()
            for finding in stored:
                if finding.status == "satisfied" or finding.rule_id == SITREP_RULE:
                    continue
                described = network.describe(finding.entity_id)
                label = f"{finding.entity_id} {described[1]}" if described else finding.entity_id
                session.add(
                    PackageItem(
                        advisory_no=advisory.advisory_no,
                        finding_id=finding.id or 0,
                        rule_id=finding.rule_id,
                        entity_id=finding.entity_id,
                        kind="conflict" if finding.status == "conflict" else "gap",
                        proposed_action=proposed_action(
                            finding.rule_id,
                            label,
                            finding.details,
                            finding.cites if finding.status == "conflict" else None,
                        ),
                        owner_role=finding.owner_role,
                        status="pending",
                    )
                )
            counts = {
                s: sum(1 for f in findings if f.status == s)
                for s in ("open", "conflict", "satisfied")
            }
            record(
                session,
                "system",
                "rules_evaluated",
                f"Playbook evaluated: {counts['open']} gaps, {counts['conflict']} conflicts, "
                f"{counts['satisfied']} satisfied",
                advisory,
                counts,
                versions,
            )
        return {}

    def draft(state: CycleState) -> CycleState:
        with unit() as session:
            advisory = advisory_of(session, state)
            package = session.get(DecisionPackage, advisory.advisory_no)
            if package is None:
                raise DataNotLoaded(f"no decision package for advisory {advisory.advisory_no}")
            items = session.exec(
                select(PackageItem).where(PackageItem.advisory_no == advisory.advisory_no)
            ).all()
            level = activation_level(advisory.hours_to_landfall, playbook.levels)
            package.draft = template_draft(advisory, level, package.changes, list(items))
            session.add(package)
            record(
                session,
                "agent",
                "sitrep_drafted",
                f"Draft situation report written ({package.draft['provider']})",
                advisory,
                {"items": len(items)},
                versions,
            )
        return {}

    def pending(advisory_no: int) -> list[int]:
        with Session(engine) as session:
            return [
                i.id or 0
                for i in session.exec(
                    select(PackageItem).where(
                        PackageItem.advisory_no == advisory_no, PackageItem.status == "pending"
                    )
                )
            ]

    def await_approval(state: CycleState) -> Command[str]:
        waiting = pending(state["advisory_no"])
        if not waiting:
            return Command(goto="finalise")
        decision = interrupt({"advisory_no": state["advisory_no"], "pending_items": len(waiting)})
        return Command(goto="apply_decision", update={"decision": decision})

    def apply_decision(state: CycleState) -> Command[str]:
        decision = state["decision"]
        with unit() as session:
            advisory = advisory_of(session, state)
            if decision.get("action") == "expire":
                items = session.exec(
                    select(PackageItem).where(
                        PackageItem.advisory_no == advisory.advisory_no,
                        PackageItem.status == "pending",
                    )
                ).all()
                for undecided in items:
                    undecided.status = "not_decided"
                    session.add(undecided)
                record(
                    session,
                    "system",
                    "items_not_decided",
                    f"{len(items)} items closed as not decided when the next advisory arrived",
                    advisory,
                    {"items": [i.id for i in items]},
                    versions,
                )
                return Command(goto="finalise")
            item = session.get(PackageItem, decision["item_id"])
            finding = session.get(Finding, item.finding_id) if item else None
            if item is None or finding is None:
                raise DataNotLoaded(f"package item {decision['item_id']} missing")
            request = decisions.DecisionRequest(
                role=decision["role"], action=decision["action"], reason=decision.get("reason")
            )
            level = activation_level(advisory.hours_to_landfall, playbook.levels)
            try:
                decisions.check(item, request, level == "full")
            except AppError as refused:
                # Normally refused before resuming; never leave the thread stuck on a refusal.
                record(
                    session,
                    "system",
                    "decision_refused",
                    str(refused),
                    advisory,
                    {"item_id": item.id, **decision},
                    versions,
                )
                return Command(goto="await_approval")
            written = decisions.apply(session, item, request, rules[item.rule_id], finding)
            record(
                session,
                "human",
                "decision",
                f"{request.role.replace('_', ' ').capitalize()} {item.status} "
                f"{item.rule_id} for {item.entity_id}"
                + (f": {item.reason}" if item.reason else ""),
                advisory,
                {
                    "item_id": item.id,
                    "rule_id": item.rule_id,
                    "entity_id": item.entity_id,
                    "action": request.action,
                    "reason": item.reason,
                    "state_written": written,
                },
                versions,
            )
        return Command(goto="await_approval")

    def finalise(state: CycleState) -> CycleState:
        with unit() as session:
            advisory = advisory_of(session, state)
            package = session.get(DecisionPackage, advisory.advisory_no)
            if package is not None:
                package.status = "closed"
                package.closed_at = datetime.now(UTC)
                session.add(package)
            record(
                session,
                "system",
                "package_finalised",
                f"Decision package for advisory {advisory.advisory_no} closed",
                advisory,
                {},
                versions,
            )
        return {}

    graph = StateGraph(CycleState)
    nodes: list[tuple[str, Callable[..., Any]]] = [
        ("load_context", load_context),
        ("diff", diff),
        ("evaluate_rules", evaluate_rules),
        ("draft", draft),
        ("await_approval", await_approval),
        ("apply_decision", apply_decision),
        ("finalise", finalise),
    ]
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "diff")
    graph.add_edge("diff", "evaluate_rules")
    graph.add_edge("evaluate_rules", "draft")
    graph.add_edge("draft", "await_approval")
    graph.add_edge("finalise", END)
    return graph
