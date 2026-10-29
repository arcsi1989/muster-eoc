"""The decision package lifecycle: the one answer to "is the package for this advisory open",
and the path every decision on its items takes.

The package row's status is the record (ADR 0001); the advisory cycle's checkpoint is the
adapter for the approval pause, and only this module reads whether it is waiting. A package
opens when its advisory is issued and stays open until the next advisory expires it.

Every decision on a package takes the same path: item decisions, situation report approval and
activation declarations are checked here, under the cycle's lock and before anything changes
(so a refusal changes nothing), and then the cycle's decision step applies them. That step is
the only writer of decided operational state; besides it, only the initial load, a scenario
reset and the per-advisory flag reset when an advisory is issued write operational state. A
declaration is the only code that sets the activation level.
"""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, select

from app import advisory_context
from app.agent import decisions, sitrep
from app.agent.cycle import AdvisoryCycle
from app.errors import AppError, ConflictError, DataNotLoaded, NotFound
from app.models import Advisory, DecisionPackage, Finding, PackageItem, PackageStatus, Sitrep
from app.network import load_network
from app.playbook.activation import PROPOSAL_RULE
from app.playbook.service import Playbook
from app.replay import service
from app.scoring_config import ScoringConfig


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
    changes: dict[str, Any]
    sitrep: Sitrep | None


def issue_next_advisory(session: Session, config: ScoringConfig, cycle: AdvisoryCycle) -> int:
    """Expires the current advisory's package, issues and scores the next advisory, and opens
    its package: the cycle runs until it pauses for decisions."""
    expire(session, cycle, advisory_context.current_advisory_no(session))
    advisory = service.advance(session, config)
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
    network = load_network(session)
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
        described = network.describe(item.entity_id)
        name = described[1] if described else None
        if name is None and (area := service.staging_area_name(session, item.entity_id)):
            name = area
        return ItemView(
            item, titles[item.rule_id], name, finding.severity, finding.cites, finding.overdue
        )

    return PackageView(
        package=package,
        status=status,
        activation_level=context.activation_level,
        proposed_activation_level=context.proposed_activation_level,
        decides_as_commander=context.commander,
        items=[view(i) for i in items],
        changes=package.changes,
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
