"""The decision package lifecycle: the one answer to "is the package for this advisory open",
and the path every decision on its items takes.

The package row's status is the record (ADR 0001); the advisory cycle's checkpoint is the
adapter for the approval pause, and only this module reads whether it is waiting. A package
opens when its advisory is issued and stays open until the next advisory expires it.

Every decision on a package takes the same path: item decisions, situation report approval,
activation declarations, field supervisors' reports on field tasks and the planning draft's
release approvals are checked here, under the cycle's lock and before anything changes (so a
refusal changes nothing), and then the cycle's decision step applies them. That step is the only
writer of decided operational state; besides it, only the initial load, a scenario reset and the
per-advisory flag reset when an advisory is issued write operational state. A declaration is the
only code that sets the activation level. The planning draft for the next operational period is
written while the package is open.

The cycle's steps do their work here too (`CycleSteps`): opening the package and its items,
saving the draft, applying decisions, expiring and closing, and the audit record of each. The
LangGraph graph keeps only the order of the steps and the pause for decisions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import Session, col, select

from app import advisory_context
from app.agent import decisions, field, sitrep
from app.agent.draft import produce_draft, sitrep_prompt
from app.agent.draft_request import draft_request
from app.audit.log import record
from app.challenger.model import ChallengerModel
from app.errors import AppError, ConflictError, DataNotLoaded, NotFound
from app.llm.grounded import GroundedOutcome
from app.llm.provider import LLMProvider
from app.llm.schemas import DraftRequest, DraftResult, PackageDraft
from app.llm.template import TemplateProvider
from app.models import (
    Advisory,
    DecisionPackage,
    Finding,
    OpState,
    PackageItem,
    PackageStatus,
    PlanningDraft,
    Score,
    Sitrep,
)
from app.planning import service as planning
from app.playbook.activation import LEVEL_NUMBER, PROPOSAL_RULE, activation_proposal
from app.playbook.package import SITREP_RULE, package_items, satisfying_state
from app.playbook.service import (
    Playbook,
    entity_names,
    reevaluate,
    store_findings,
    store_new_event_findings,
)
from app.replay import service
from app.scoring_config import ScoringConfig

if TYPE_CHECKING:  # the cycle runs the graph, whose steps call back into this module
    from app.agent.cycle import AdvisoryCycle

# what resumes the approval pause besides an item decision (whose action is the person's)
EXPIRE = "expire"
DECLARE = "declare"
APPROVE_SITREP = "approve_sitrep"
RELEASE = "release_planning"


class PackageClosed(ConflictError):
    code = "package_closed"


class PackageOutOfStep(AppError):
    """The package record and the cycle's approval pause disagree: a bug, never a refusal."""

    code = "package_out_of_step"


class NoActivationProposal(ConflictError):
    code = "no_activation_proposal"


@dataclass(frozen=True)
class ItemView:
    item: PackageItem
    title: str
    entity_name: str | None
    severity: str
    cites: list[str]
    overdue: bool


@dataclass(frozen=True)
class PackageView:
    package: DecisionPackage
    status: PackageStatus  # the lifecycle's answer to "is it open"
    activation_level: str | None
    proposed_activation_level: str | None
    decides_as_commander: advisory_context.Commander
    items: list[ItemView]
    sitrep: Sitrep | None


def issue_next_advisory(
    session: Session,
    config: ScoringConfig,
    cycle: AdvisoryCycle,
    challenger: ChallengerModel | None = None,
) -> int:
    """Expires the current advisory's package, issues and scores the next advisory (the
    challenger, if loaded, in shadow), and opens its package: the cycle runs until it pauses for
    decisions."""
    expire(session, cycle, advisory_context.current_advisory_no(session))
    advisory = service.advance(session, config, challenger)
    advisory_context.reset_per_advisory_flags(session, advisory)
    session.commit()  # one transaction: the advisory is never current with stale flags
    cycle.start(advisory.advisory_no)
    return advisory.advisory_no


def expire(session: Session, cycle: AdvisoryCycle, advisory_no: int) -> None:
    """Closes the package's undecided items as not decided and closes the package."""
    if advisory_no and is_open(session, cycle, advisory_no):
        cycle.expire(advisory_no)


def is_open(session: Session, cycle: AdvisoryCycle, advisory_no: int) -> bool:
    """Whether the package for `advisory_no` takes decisions. Raises PackageOutOfStep if its
    record and the cycle disagree."""
    package = session.get(DecisionPackage, advisory_no)
    if package is None:
        return False
    with cycle.between_steps():  # never mid-step, between a step's commit and its checkpoint
        session.refresh(package)
        recorded = package.status == "open"
        waiting = cycle.waiting(advisory_no)
    if recorded != waiting:
        raise PackageOutOfStep(
            f"the decision package for advisory {advisory_no} is recorded {package.status} but "
            "its cycle disagrees"
        )
    return recorded


def _require_open(session: Session, cycle: AdvisoryCycle, advisory_no: int) -> None:
    if not is_open(session, cycle, advisory_no):
        raise PackageClosed(f"the decision package for advisory {advisory_no} is closed")


def _commander_if_open(
    session: Session, playbook: Playbook, cycle: AdvisoryCycle, advisory: Advisory
) -> advisory_context.Commander:
    """The role that commands at `advisory`, read fresh; raises PackageClosed if its package is
    closed. Called under the cycle's lock, before a decision is checked."""
    _require_open(session, cycle, advisory.advisory_no)
    session.expire_all()
    return advisory_context.at(session, playbook.levels, advisory).commander


def package_view(
    session: Session, playbook: Playbook, cycle: AdvisoryCycle, advisory_no: int
) -> PackageView:
    advisory = service.require_issued(session, advisory_no)
    package = session.get(DecisionPackage, advisory_no)
    if package is None:
        raise NotFound(f"no decision package for advisory {advisory_no}")
    status: PackageStatus = "open" if is_open(session, cycle, advisory_no) else "closed"
    titles = {r.id: r.title for r in playbook.rulebook.rules}
    names = entity_names(session)
    findings = {
        f.id: f for f in session.exec(select(Finding).where(Finding.advisory_no == advisory_no))
    }
    items = session.exec(
        select(PackageItem)
        .where(PackageItem.advisory_no == advisory_no)
        .order_by(col(PackageItem.id))
    ).all()
    context = advisory_context.at(session, playbook.levels, advisory)

    def view(item: PackageItem) -> ItemView:
        finding = findings[item.finding_id]
        return ItemView(
            item,
            titles[item.rule_id],
            names.get(item.entity_id),
            finding.severity,
            finding.cites,
            finding.overdue,
        )

    return PackageView(
        package=package,
        status=status,
        activation_level=context.activation_level,
        proposed_activation_level=context.proposed_activation_level,
        decides_as_commander=context.commander,
        items=[view(i) for i in items],
        sitrep=session.get(Sitrep, advisory_no),
    )


def decide(
    session: Session,
    playbook: Playbook,
    cycle: AdvisoryCycle,
    advisory_no: int,
    item_id: int,
    request: decisions.DecisionRequest,
) -> None:
    """Checks the decision once, before anything changes (so a refusal changes nothing): the
    package is open, then the decision rules for the role that commands at the advisory's
    activation level. Then the cycle applies it."""
    advisory = service.require_issued(session, advisory_no)
    item = session.get(PackageItem, item_id)
    if item is None or item.advisory_no != advisory_no:
        raise NotFound(f"no item {item_id} in the package for advisory {advisory_no}")

    def precheck() -> None:  # under the cycle's lock, so two decisions cannot both pass
        lead = _commander_if_open(session, playbook, cycle, advisory)
        decisions.check(item, request, lead)

    cycle.decide(advisory_no, item_id, request, precheck)
    session.expire_all()


def approve_sitrep(
    session: Session,
    playbook: Playbook,
    cycle: AdvisoryCycle,
    advisory_no: int,
    role: decisions.Role,
    text: str,
) -> Sitrep:
    """Approves the (possibly edited) situation report behind the same gate as an item decision:
    the package is open, then the role that commands at the advisory approves. Then the cycle
    applies it, which satisfies P-7.1."""
    advisory = service.require_issued(session, advisory_no)

    def precheck() -> None:  # under the cycle's lock, so two approvals cannot both pass
        lead = _commander_if_open(session, playbook, cycle, advisory)
        sitrep.check_approval(session, advisory_no, role, text, lead)

    cycle.approve_sitrep(advisory_no, role, text, precheck)
    session.expire_all()
    approved = session.get(Sitrep, advisory_no)
    if approved is None:
        raise DataNotLoaded(f"the situation report for advisory {advisory_no} was not recorded")
    return approved


def declare(session: Session, cycle: AdvisoryCycle, declaration: decisions.Declaration) -> int:
    """Declares an activation level on the current advisory's P-2.5 proposal: checked first (so
    a refusal changes nothing), then the cycle records it. Returns the advisory number."""
    advisory_no = advisory_context.current_advisory_no(session)
    if not advisory_no or not is_open(session, cycle, advisory_no):
        raise PackageClosed("no decision package is open; a level is declared on its proposal")
    item = session.exec(
        select(PackageItem).where(
            PackageItem.advisory_no == advisory_no, PackageItem.rule_id == PROPOSAL_RULE
        )
    ).first()
    if item is None:
        raise NoActivationProposal(
            f"advisory {advisory_no} proposes no change of activation level (P-2.5)"
        )
    finding = session.get(Finding, item.finding_id)
    if finding is None:
        raise DataNotLoaded(f"finding {item.finding_id} missing")

    def precheck() -> None:  # under the cycle's lock
        _require_open(session, cycle, advisory_no)
        session.refresh(item)
        decisions.check_declaration(item, finding, declaration)

    cycle.declare(advisory_no, item.id or 0, declaration, precheck)
    session.expire_all()
    return advisory_no


def draft_planning(
    session: Session,
    playbook: Playbook,
    cycle: AdvisoryCycle,
    config: ScoringConfig,
    llm: LLMProvider,
    advisory_no: int,
) -> PlanningDraft:
    """Drafts the ICS-215 and IAP objectives for the period after `advisory_no` from its
    package's decisions so far, while the package is open and the draft is not yet approved."""
    advisory = service.require_issued(session, advisory_no)
    _require_open(session, cycle, advisory_no)
    planning.check_redraft(session, advisory_no)
    fallback = TemplateProvider.from_config(config)
    drafted = planning.draft(session, advisory, playbook, config.planning, llm, fallback)
    session.commit()
    session.refresh(drafted)
    return drafted


def release_planning(
    session: Session,
    playbook: Playbook,
    cycle: AdvisoryCycle,
    advisory_no: int,
    role: decisions.Role,
) -> PlanningDraft:
    """The next release approval of the planning draft, behind the same gate as an item
    decision: the package is open, then the Planning Section Chief approves and the role that
    commands at the advisory releases. Then the cycle records it."""
    advisory = service.require_issued(session, advisory_no)

    def precheck() -> None:  # under the cycle's lock, so two approvals cannot both pass
        lead = _commander_if_open(session, playbook, cycle, advisory)
        planning.check_release(session, advisory_no, role, lead)

    cycle.release_planning(advisory_no, role, precheck)
    session.expire_all()
    return planning.require_draft(session, advisory_no)


def report_field_work(
    session: Session,
    playbook: Playbook,
    cycle: AdvisoryCycle,
    item_id: int,
    request: field.FieldReportRequest,
) -> int:
    """A field supervisor reports a field task done or blocked, at the current advisory, behind
    the same gate as a decision: checked first (the current package is open, the task is in the
    supervisor's district, Done is not under stop-work), then the cycle applies it. Returns the
    advisory number."""
    advisory_no = advisory_context.current_advisory_no(session)
    if not advisory_no or not is_open(session, cycle, advisory_no):
        raise PackageClosed("no decision package is open; field work is reported during one")
    advisory = service.require_issued(session, advisory_no)

    def precheck() -> None:  # under the cycle's lock, so two reports cannot both pass
        _require_open(session, cycle, advisory_no)
        session.expire_all()
        field.check(session, playbook, advisory, item_id, request)

    cycle.report_field_work(advisory_no, item_id, request, precheck)
    session.expire_all()
    return advisory_no


class CycleSteps:
    """The work of each advisory cycle step, one transaction each (the graph opens it). Every
    step writes its audit event."""

    def __init__(self, playbook: Playbook, llm: LLMProvider, config: ScoringConfig) -> None:
        self._playbook = playbook
        self._llm = llm
        self._config = config
        self._fallback = TemplateProvider.from_config(config)
        self._prompt = sitrep_prompt(config.draft)

    def _versions(
        self, session: Session, advisory: Advisory, prompt_version: str | None = None
    ) -> dict[str, Any]:
        """The versions that produced a step: the model version is the one that scored the
        advisory; a prompt version only for the step a prompt wrote."""
        return {
            "rules_version": self._playbook.rulebook.version,
            "model_version": service.model_version(session, advisory.advisory_no),
            "prompt_version": prompt_version,
        }

    @staticmethod
    def _advisory(session: Session, advisory_no: int) -> Advisory:
        advisory = session.get(Advisory, advisory_no)
        if advisory is None:
            raise DataNotLoaded(f"advisory {advisory_no} missing")
        return advisory

    @staticmethod
    def _package(session: Session, advisory_no: int) -> DecisionPackage:
        package = session.get(DecisionPackage, advisory_no)
        if package is None:
            raise DataNotLoaded(f"no decision package for advisory {advisory_no}")
        return package

    def load_context(self, session: Session, advisory_no: int) -> None:
        """Records what the advisory's cycle starts from: the top risks, the event state and
        the activation level."""
        advisory = self._advisory(session, advisory_no)
        top10 = session.exec(
            select(Score.asset_id)
            .where(Score.advisory_no == advisory_no, Score.rank <= self._config.risk.top_n)
            .order_by(col(Score.rank))
        ).all()
        event_state = {
            s.key: s.value for s in session.exec(select(OpState).where(OpState.entity == "event"))
        }
        level = advisory_context.at(session, self._playbook.levels, advisory).activation_level
        record(
            session,
            "system",
            "context_loaded",
            f"Advisory {advisory_no} loaded: {advisory.hours_to_landfall} h to landfall, {level}",
            advisory,
            {"top10": list(top10), "event_state": event_state, "activation_level": level},
            self._versions(session, advisory),
        )

    def open_package(self, session: Session, advisory_no: int) -> None:
        """Opens the advisory's package with what changed since the previous advisory."""
        advisory = self._advisory(session, advisory_no)
        top_n = self._config.risk.top_n
        changes = service.changes(session, advisory_no, self._playbook.levels, top_n)
        session.merge(
            DecisionPackage(
                advisory_no=advisory_no,
                status="open",
                changes=changes,
                opened_at=datetime.now(UTC),
            )
        )
        moves = len(changes.rank_moves)
        record(
            session,
            "system",
            "diff",
            f"Compared with advisory {changes.previous_advisory_no or '-'}: {moves} rank moves",
            advisory,
            changes.model_dump(mode="json"),
            self._versions(session, advisory),
        )

    def _add_items(
        self, session: Session, advisory: Advisory, stored: Sequence[Finding]
    ) -> list[str]:
        """Adds a pending item for each package item the playbook proposes for `stored`, with
        the note of earlier work on it reported blocked; returns their rule IDs."""
        proposals = package_items(session, self._playbook, stored)
        blocked = field.blocked_notes(session, advisory.advisory_no)
        session.add_all(
            PackageItem(
                advisory_no=advisory.advisory_no,
                finding_id=p.finding.id or 0,
                rule_id=p.finding.rule_id,
                entity_id=p.finding.entity_id,
                kind=p.kind,
                proposed_action=p.proposed_action,
                owner_role=p.owner_role,
                status="pending",
                blocked_note=blocked.get((p.finding.rule_id, p.finding.entity_id)),
            )
            for p in proposals
        )
        return [p.finding.rule_id for p in proposals]

    def evaluate_rules(self, session: Session, advisory_no: int) -> None:
        """Evaluates the playbook and adds the package's items."""
        advisory = self._advisory(session, advisory_no)
        findings = store_findings(session, advisory, self._playbook)
        session.flush()
        stored = session.exec(select(Finding).where(Finding.advisory_no == advisory_no)).all()
        self._add_items(session, advisory, stored)
        counts = {
            s: sum(1 for f in findings if f.status == s) for s in ("open", "conflict", "satisfied")
        }
        record(
            session,
            "system",
            "rules_evaluated",
            f"Playbook evaluated: {counts['open']} gaps, {counts['conflict']} conflicts, "
            f"{counts['satisfied']} satisfied",
            advisory,
            counts,
            self._versions(session, advisory),
        )

    def draft_request(self, session: Session, advisory_no: int) -> DraftRequest:
        """What the draft situation report may see."""
        advisory = self._advisory(session, advisory_no)
        changes = self._package(session, advisory_no).changes
        return draft_request(session, advisory, self._playbook, changes, self._config.draft)

    def write_draft(self, request: DraftRequest) -> GroundedOutcome[DraftResult]:
        """The provider's grounded draft, else the template's. Runs outside any transaction."""
        attempts = 1 + self._config.draft.retries
        return produce_draft(self._llm, self._fallback, self._prompt, request, attempts)

    def save_draft(
        self,
        session: Session,
        advisory_no: int,
        request: DraftRequest,
        outcome: GroundedOutcome[DraftResult],
    ) -> None:
        advisory = self._advisory(session, advisory_no)
        package = self._package(session, advisory_no)
        package.draft = PackageDraft(
            provider=outcome.provider,
            fallback=outcome.fallback,
            model=outcome.result.model,
            prompt_version=outcome.prompt_version,
            fallback_reason=outcome.fallback_reason,
            sections=outcome.result.draft.sections,
        )
        session.add(package)
        record(
            session,
            "agent",
            "sitrep_drafted",
            f"Draft situation report written by {outcome.provider}"
            + (f" ({outcome.fallback_reason})" if outcome.fallback_reason else ""),
            advisory,
            {
                "provider": outcome.provider,
                "model": outcome.result.model,
                "attempts": outcome.attempts,
                "fallback_reason": outcome.fallback_reason,
                "clauses_retrieved": [c.id for c in request.clauses],
            },
            self._versions(session, advisory, outcome.prompt_version),
        )

    @staticmethod
    def pending_count(session: Session, advisory_no: int) -> int:
        return len(_pending(session, advisory_no))

    def apply(self, session: Session, advisory_no: int, decision: dict[str, Any]) -> bool:
        """Applies a decision the lifecycle checked: an item decision, a declaration, the
        situation report approval, a field report, a planning release approval, or the next
        advisory expiring the package. The only writer of decided operational state. Returns True
        when the package's decisions are over."""
        advisory = self._advisory(session, advisory_no)
        action = decision.get("action")
        if action == EXPIRE:
            self._expire_items(session, advisory)
            return True
        if action == RELEASE:
            planning.apply_release(session, advisory, decision["role"])
            return False
        if action == APPROVE_SITREP:
            sitrep.apply_approval(session, advisory, decision["role"], decision["text"])
            session.flush()
            reevaluate(session, advisory, self._playbook, SITREP_RULE)
            return False
        if action == field.FIELD_REPORT:
            self._report_field(session, advisory, decision)
            return False
        item = session.get(PackageItem, decision["item_id"])
        finding = session.get(Finding, item.finding_id) if item else None
        if item is None or finding is None:
            raise DataNotLoaded(f"package item {decision['item_id']} missing")
        if action == DECLARE:
            self._declare(session, advisory, item, finding, decision)
        else:
            self._decide(session, advisory, item, finding, decision)
        return False

    def _expire_items(self, session: Session, advisory: Advisory) -> None:
        items = _pending(session, advisory.advisory_no)
        for undecided in items:
            undecided.status = "not_decided"
            session.add(undecided)
        if items:  # nothing to record when every item was decided
            record(
                session,
                "system",
                "items_not_decided",
                f"{len(items)} items closed as not decided when the next advisory arrived",
                advisory,
                {
                    "items": [
                        {"id": i.id, "rule_id": i.rule_id, "entity_id": i.entity_id} for i in items
                    ]
                },
                self._versions(session, advisory),
            )

    def _decide(
        self,
        session: Session,
        advisory: Advisory,
        item: PackageItem,
        finding: Finding,
        decision: dict[str, Any],
    ) -> None:
        request = decisions.DecisionRequest(
            role=decision["role"], action=decision["action"], reason=decision.get("reason")
        )
        satisfying = satisfying_state(self._playbook, finding)
        written = decisions.apply(session, item, request, satisfying)
        record(
            session,
            "human",
            "decision",
            f"{decisions.role_label(request.role)} {item.status} "
            f"{item.rule_id} for {item.entity_id}" + (f": {item.reason}" if item.reason else ""),
            advisory,
            {
                "item_id": item.id,
                "role": request.role,
                "rule_id": item.rule_id,
                "entity_id": item.entity_id,
                "action": request.action,
                "reason": item.reason,
                "state_written": written,
            },
            self._versions(session, advisory),
        )

    def _declare(
        self,
        session: Session,
        advisory: Advisory,
        item: PackageItem,
        finding: Finding,
        decision: dict[str, Any],
    ) -> None:
        """Declares the activation level on the P-2.5 item, then adds the event items the new
        level brings (P-7.2 once Full is declared)."""
        declaration = decisions.Declaration(
            level=decision["level"], declared_by=decision["declared_by"], reason=decision["reason"]
        )
        written = decisions.declare(session, item, declaration, advisory)
        session.flush()
        added = self._add_items(
            session, advisory, store_new_event_findings(session, advisory, self._playbook)
        )
        record(
            session,
            "human",
            "activation_declared",
            f"{decisions.role_label(declaration.declared_by)} declared activation "
            f"Level {LEVEL_NUMBER[declaration.level]} ({declaration.level})"
            + (f": {item.reason}" if item.reason else ""),
            advisory,
            {
                "item_id": item.id,
                "role": declaration.declared_by,
                "rule_id": item.rule_id,
                "entity_id": item.entity_id,
                "level": declaration.level,
                "from_level": activation_proposal(finding.details).declared,
                "reason": item.reason,
                "state_written": written,
                "items_added": added,
            },
            self._versions(session, advisory),
        )

    def _report_field(self, session: Session, advisory: Advisory, decision: dict[str, Any]) -> None:
        request = field.FieldReportRequest.from_resume(decision)
        task, written = field.apply(session, self._playbook, advisory, decision["item_id"], request)
        item = task.work.item
        note = request.note
        record(
            session,
            field.FIELD_SUPERVISOR,
            f"field_task_{request.outcome}",
            f"Field supervisor ({request.district}) reported {item.rule_id} for {item.entity_id} "
            f"{request.outcome}" + (f": {note}" if note else ""),
            advisory,
            {
                "item_id": item.id,
                "rule_id": item.rule_id,
                "entity_id": item.entity_id,
                "district": request.district,
                "outcome": request.outcome,
                "note": note,
                "state_written": written,
            },
            self._versions(session, advisory),
        )

    def close(self, session: Session, advisory_no: int) -> None:
        """Closes the package once its advisory expired."""
        advisory = self._advisory(session, advisory_no)
        package = session.get(DecisionPackage, advisory_no)
        if package is not None:
            package.status = "closed"
            package.closed_at = datetime.now(UTC)
            session.add(package)
        record(
            session,
            "system",
            "package_finalised",
            f"Decision package for advisory {advisory_no} closed",
            advisory,
            {},
            self._versions(session, advisory),
        )


def _pending(session: Session, advisory_no: int) -> list[PackageItem]:
    return list(
        session.exec(
            select(PackageItem).where(
                PackageItem.advisory_no == advisory_no, PackageItem.status == "pending"
            )
        )
    )
