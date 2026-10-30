"""Runs the advisory cycle graph: one LangGraph thread per advisory, checkpointed in its own
SQLite file (ADR 0001)."""

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import Engine
from sqlmodel import Session, delete

from app.agent.decisions import DecisionRequest, Declaration, Role
from app.agent.field import FieldReportRequest
from app.agent.graph import build_graph
from app.agent.lifecycle import APPROVE_SITREP, DECLARE, EXPIRE, RELEASE
from app.audit.log import clear_events, record
from app.calibration.service import CALIBRATION_EVENT
from app.calibration.versions import APPROVED_EVENT
from app.evals.audit import EVALUATION_EVENT
from app.llm.provider import LLMProvider
from app.models import DecisionPackage, FieldReport, PackageItem, Sitrep
from app.planning.service import clear as clear_planning
from app.playbook.service import Playbook, clear_findings
from app.replay import service
from app.scoring_config import ScoringConfig
from app.tracing import store as tracing


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
        # one graph step at a time on the shared connection; reentrant so a check that runs
        # under it (a decision's precheck) can read between steps too
        self._lock = threading.RLock()

    @staticmethod
    def _thread(advisory_no: int) -> Any:
        return {"configurable": {"thread_id": f"advisory-{advisory_no}"}}

    def start(self, advisory_no: int) -> None:
        with self._lock:
            self._graph.invoke({"advisory_no": advisory_no}, self._thread(advisory_no))

    @contextmanager
    def between_steps(self) -> Iterator[None]:
        """Holds the cycle between graph steps, so a read sees a step's database writes and its
        checkpoint together."""
        with self._lock:
            yield

    def waiting(self, advisory_no: int) -> bool:
        """True while the advisory's thread is paused for decisions. Read only by the decision
        package lifecycle, which keeps it in step with the package record."""
        with self._lock:
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
        resume = {"item_id": item_id, "action": DECLARE, **asdict(declaration)}
        self._resume(advisory_no, resume, precheck)

    def approve_sitrep(
        self, advisory_no: int, role: Role, text: str, precheck: Callable[[], None]
    ) -> None:
        """Like `decide`, for approving the advisory's situation report."""
        resume = {"action": APPROVE_SITREP, "role": role, "text": text}
        self._resume(advisory_no, resume, precheck)

    def release_planning(self, advisory_no: int, role: Role, precheck: Callable[[], None]) -> None:
        """Like `decide`, for a release approval of the advisory's planning draft."""
        self._resume(advisory_no, {"action": RELEASE, "role": role}, precheck)

    def report_field_work(
        self,
        advisory_no: int,
        item_id: int,
        request: FieldReportRequest,
        precheck: Callable[[], None],
    ) -> None:
        """Like `decide`, for a field supervisor's report on a field task."""
        self._resume(advisory_no, request.to_resume(item_id), precheck)

    def _resume(
        self, advisory_no: int, resume: dict[str, Any], precheck: Callable[[], None]
    ) -> None:
        with self._lock:
            precheck()
            self._graph.invoke(Command(resume=resume), self._thread(advisory_no))

    def expire(self, advisory_no: int) -> None:
        """Resumes the paused thread to close undecided items as not decided and finalise the
        package. Does nothing if the thread is not paused."""
        with self._lock:
            if self.waiting(advisory_no):
                self._graph.invoke(Command(resume={"action": EXPIRE}), self._thread(advisory_no))

    def reset(self, session: Session) -> None:
        """Deletes every advisory's thread and the decision packages, their items, field reports
        and situation reports."""
        with self._lock:
            for advisory_no in range(1, service.total_advisories(session) + 1):
                self._saver.delete_thread(f"advisory-{advisory_no}")
            session.exec(delete(Sitrep))
            session.exec(delete(FieldReport))
            session.exec(delete(PackageItem))
            session.exec(delete(DecisionPackage))

    def close(self) -> None:
        self._conn.close()


def reset_scenario(session: Session, cycle: AdvisoryCycle, data_dir: Path) -> None:
    """Back to before advisory 1: checkpoints deleted, decisions, findings, the audit log and
    the traces cleared (a new demo run begins), the operational state restored from the initial
    state. Each module clears its own tables. Model versions are not scenario state: they, their
    calibration runs and approvals, and the latest evaluation stay, so the replay scores with the
    approved version and the log still shows who approved it and how it was evaluated."""
    clear_planning(session)
    cycle.reset(session)
    clear_findings(session)
    clear_events(session, keep=(CALIBRATION_EVENT, APPROVED_EVENT, EVALUATION_EVENT))
    tracing.clear(session)
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
