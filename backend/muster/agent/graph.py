"""The advisory cycle as a LangGraph StateGraph (plan section 4, ADR 0001).

load_context -> diff -> evaluate_rules -> draft -> await_approval <-> apply_decision -> finalise

The graph holds only orchestration: the order of the steps, one transaction per step, and the
pause for decisions. Each step's work and its audit event are the decision package lifecycle's
(`CycleSteps`). The thread pauses in `await_approval` until the next advisory expires it, so the
package stays open while its advisory is current. The lifecycle checks every decision before
resuming; `apply_decision` applies it. Only `apply_decision` writes decided operational state
(item decisions, situation report approvals and activation declarations), and it is
deterministic: the LLM never writes state, never decides whether a rule is met and never changes
scores. The graph state holds only the advisory number and the decision being applied; the
package, its items and the findings live in the database. Every node runs inside a tracing span.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import Engine
from sqlmodel import Session

from muster.agent.lifecycle import CycleSteps
from muster.llm.provider import LLMProvider
from muster.playbook.service import Playbook
from muster.scoring_config import ScoringConfig
from muster.tracing.instrument import cycle_node


class CycleState(TypedDict, total=False):
    advisory_no: int
    decision: dict[str, Any]


def build_graph(
    engine: Engine, playbook: Playbook, llm: LLMProvider, config: ScoringConfig
) -> StateGraph[CycleState]:
    steps = CycleSteps(playbook, llm, config)

    @contextmanager
    def unit() -> Iterator[Session]:
        with Session(engine) as session:
            yield session
            session.commit()

    def load_context(state: CycleState) -> CycleState:
        with unit() as session:
            steps.load_context(session, state["advisory_no"])
        return {}

    def diff(state: CycleState) -> CycleState:
        with unit() as session:
            steps.open_package(session, state["advisory_no"])
        return {}

    def evaluate_rules(state: CycleState) -> CycleState:
        with unit() as session:
            steps.evaluate_rules(session, state["advisory_no"])
        return {}

    def draft(state: CycleState) -> CycleState:
        with unit() as session:
            request = steps.draft_request(session, state["advisory_no"])
        # the model call runs outside any database transaction
        outcome = steps.write_draft(request)
        with unit() as session:
            steps.save_draft(session, state["advisory_no"], request, outcome)
        return {}

    def await_approval(state: CycleState) -> Command[str]:
        """Pauses even with every item decided: the situation report may still be approved."""
        with Session(engine) as session:  # a read: nothing to commit
            waiting = steps.pending_count(session, state["advisory_no"])
        decision = interrupt({"advisory_no": state["advisory_no"], "pending_items": waiting})
        return Command(goto="apply_decision", update={"decision": decision})

    def apply_decision(state: CycleState) -> Command[str]:
        with unit() as session:
            ended = steps.apply(session, state["advisory_no"], state["decision"])
        return Command(goto="finalise" if ended else "await_approval")

    def finalise(state: CycleState) -> CycleState:
        with unit() as session:
            steps.close(session, state["advisory_no"])
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
        graph.add_node(name, _traced(name, node))
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "diff")
    graph.add_edge("diff", "evaluate_rules")
    graph.add_edge("evaluate_rules", "draft")
    graph.add_edge("draft", "await_approval")
    graph.add_edge("finalise", END)
    return graph


def _traced(name: str, node: Callable[..., Any]) -> Callable[..., Any]:
    """The node, inside its span (CR-03 C3). A resumed `await_approval` runs again, so a paused
    advisory has one paused span and one more per decision."""

    def run(state: CycleState) -> Any:
        with cycle_node(state["advisory_no"], name):
            return node(state)

    return run
