"""Read side of the decision package, and the entry point for a person's decision."""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, select

from app.agent import decisions
from app.agent.cycle import AdvisoryCycle
from app.errors import ConflictError, NotFound
from app.models import DecisionPackage, Finding, PackageItem, Sitrep
from app.network import load_network
from app.playbook.activation import activation_level
from app.playbook.service import Playbook
from app.replay import service


class PackageClosed(ConflictError):
    code = "package_closed"


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
    decides_as_commander: str  # incident_commander at full activation, director below
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
    level = activation_level(advisory.hours_to_landfall, playbook.levels)

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
        activation_level=level,
        decides_as_commander=decisions.commander(level == "full"),
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
    if advisory_no != service.current_advisory(session) or not cycle.waiting(advisory_no):
        raise PackageClosed(f"the decision package for advisory {advisory_no} is closed")
    full = activation_level(advisory.hours_to_landfall, playbook.levels) == "full"

    def precheck() -> None:
        session.refresh(item)
        decisions.check(item, request, full)

    cycle.decide(advisory_no, item_id, request, precheck)
    session.expire_all()
