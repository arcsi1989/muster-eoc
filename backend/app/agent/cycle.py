"""Runs the advisory cycle graph: one LangGraph thread per advisory, checkpointed in its own
SQLite file (ADR 0001)."""

import sqlite3
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import Engine
from sqlmodel import Session, delete

from app import advisory_context
from app.agent.decisions import DecisionRequest, Declaration
from app.agent.graph import build_graph
from app.audit.log import clear_events, record
from app.calibration.service import CALIBRATION_EVENT
from app.calibration.versions import APPROVED_EVENT
from app.llm.provider import LLMProvider
from app.models import DecisionPackage, PackageItem, Sitrep
from app.playbook.service import Playbook, clear_findings
from app.replay import service
from app.scoring_config import ScoringConfig


class AdvisoryCycle:
    def __init__(
        self,
        engine: Engine,
        playbook: Playbook,
        checkpoint_path: Path,
        llm: LLMProvider,
        config: ScoringConfig,
    ) -> None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.unlink(missing_ok=True)  # every backend start begins a fresh scenario
        self._conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self._saver = SqliteSaver(self._conn)
        self._saver.setup()
        self._graph = build_graph(engine, playbook, llm, config).compile(checkpointer=self._saver)
        self._lock = threading.Lock()  # one graph step at a time on the shared connection

    @staticmethod
    def _thread(advisory_no: int) -> Any:
        return {"configurable": {"thread_id": f"advisory-{advisory_no}"}}

    def start(self, advisory_no: int) -> None:
        with self._lock:
            self._graph.invoke({"advisory_no": advisory_no}, self._thread(advisory_no))

    def waiting(self, advisory_no: int) -> bool:
        """True while the advisory's thread is paused for decisions."""
        return bool(self._graph.get_state(self._thread(advisory_no)).next)

    def decide(
        self,
        advisory_no: int,
        item_id: int,
        request: DecisionRequest,
        precheck: Callable[[], None],
    ) -> None:
        """Runs `precheck` (which raises to refuse) and resumes the thread under one lock, so two
        decisions on the same item cannot both pass the check."""
        self._resume(advisory_no, {"item_id": item_id, **asdict(request)}, precheck)

    def declare(
        self,
        advisory_no: int,
        item_id: int,
        declaration: Declaration,
        precheck: Callable[[], None],
    ) -> None:
        """Like `decide`, for an activation declaration on the P-2.5 item."""
        resume = {"item_id": item_id, "action": "declare", **asdict(declaration)}
        self._resume(advisory_no, resume, precheck)

    def _resume(
        self, advisory_no: int, resume: dict[str, Any], precheck: Callable[[], None]
    ) -> None:
        with self._lock:
            precheck()
            self._graph.invoke(Command(resume=resume), self._thread(advisory_no))

    def expire(self, advisory_no: int) -> None:
        """Closes undecided items as not decided and finalises the package."""
        with self._lock:
            if advisory_no and self.waiting(advisory_no):
                self._graph.invoke(Command(resume={"action": "expire"}), self._thread(advisory_no))

    def reset(self, session: Session) -> None:
        """Deletes every advisory's thread and the decision packages, their items and situation
        reports."""
        with self._lock:
            for advisory_no in range(1, service.total_advisories(session) + 1):
                self._saver.delete_thread(f"advisory-{advisory_no}")
            session.exec(delete(Sitrep))
            session.exec(delete(PackageItem))
            session.exec(delete(DecisionPackage))

    def close(self) -> None:
        self._conn.close()


def issue_next_advisory(session: Session, config: ScoringConfig, cycle: AdvisoryCycle) -> int:
    """Expires the current advisory's open decisions, issues and scores the next advisory, and
    runs its cycle until it pauses for decisions."""
    cycle.expire(advisory_context.current_advisory_no(session))
    advisory = service.advance(session, config)
    advisory_context.reset_per_advisory_flags(session, advisory)
    session.commit()  # one transaction: the advisory is never current with stale flags
    cycle.start(advisory.advisory_no)
    return advisory.advisory_no


def reset_scenario(session: Session, cycle: AdvisoryCycle, data_dir: Path) -> None:
    """Back to before advisory 1: checkpoints deleted, decisions, findings and the audit log
    cleared, the operational state restored from the initial state. Each module clears its own
    tables. Model versions are not scenario state: they, their calibration runs and approvals
    stay, so the replay scores with the approved version and the log still shows who approved
    it."""
    cycle.reset(session)
    clear_findings(session)
    clear_events(session, keep=(CALIBRATION_EVENT, APPROVED_EVENT))
    service.reset(session, data_dir)
    record(
        session,
        "system",
        "scenario_reset",
        "Scenario reset to before advisory 1; operational state restored from the initial state",
        None,
        {},
        {},
    )
    session.commit()
