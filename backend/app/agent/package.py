"""Read side of the decision package, and the entry point for a person's decision."""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, select

from app import advisory_context
from app.agent import decisions
from app.agent.cycle import AdvisoryCycle
from app.errors import ConflictError, DataNotLoaded, NotFound
from app.models import DecisionPackage, Finding, PackageItem, Sitrep
from app.network import load_network
from app.playbook.activation import PROPOSAL_RULE
from app.playbook.service import Playbook
from app.replay import service


class PackageClosed(ConflictError):
    code = "package_closed"


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
    activation_level: str | None
    proposed_activation_level: str | None
    decides_as_commander: advisory_context.Commander
    items: list[ItemView]
    changes: dict[str, Any]
    sitrep: Sitrep | None


def package_view(session: Session, playbook: Playbook, advisory_no: int) -> PackageView:
    advisory = service.require_issued(session, advisory_no)
    package = session.get(DecisionPackage, advisory_no)
    if package is None:
        raise NotFound(f"no decision package for advisory {advisory_no}")
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
    """Checks the decision first (so a refusal changes nothing), then resumes the cycle."""
    advisory = service.require_issued(session, advisory_no)
    item = session.get(PackageItem, item_id)
    if item is None or item.advisory_no != advisory_no:
        raise NotFound(f"no item {item_id} in the package for advisory {advisory_no}")
    if advisory_no != advisory_context.current_advisory_no(session) or not cycle.waiting(
        advisory_no
    ):
        raise PackageClosed(f"the decision package for advisory {advisory_no} is closed")
    lead = advisory_context.at(session, playbook.levels, advisory).commander

    def precheck() -> None:
        session.refresh(item)
        decisions.check(item, request, lead)

    cycle.decide(advisory_no, item_id, request, precheck)
    session.expire_all()


def declare(session: Session, cycle: AdvisoryCycle, declaration: decisions.Declaration) -> int:
    """Declares an activation level on the current advisory's P-2.5 proposal: checked first (so
    a refusal changes nothing), then the cycle records it. Returns the advisory number."""
    advisory_no = advisory_context.current_advisory_no(session)
    if not advisory_no or not cycle.waiting(advisory_no):
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

    def precheck() -> None:
        session.refresh(item)
        decisions.check_declaration(item, finding, declaration)

    cycle.declare(advisory_no, item.id or 0, declaration, precheck)
    session.expire_all()
    return advisory_no
