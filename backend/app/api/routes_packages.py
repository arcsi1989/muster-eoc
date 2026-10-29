from fastapi import APIRouter

from app.agent.decisions import DecisionRequest
from app.agent.package import PackageView, decide, package_view
from app.agent.sitrep import draft_text
from app.api.schemas import DecisionIn, PackageItemOut, PackageOut, SitrepOut
from app.deps import CycleDep, PlaybookDep, SessionDep

router = APIRouter(prefix="/packages")


def _out(view: PackageView) -> PackageOut:
    return PackageOut(
        advisory_no=view.package.advisory_no,
        status=view.package.status,
        activation_level=view.activation_level,
        decides_as_commander=view.decides_as_commander,
        changes=view.changes,  # type: ignore[arg-type]  # validated into ChangesOut
        items=[
            PackageItemOut(
                **v.item.model_dump(exclude={"advisory_no", "finding_id"}),
                title=v.title,
                entity_name=v.entity_name,
                severity=v.severity,
                cites=v.cites,
                overdue=v.overdue,
            )
            for v in view.items
        ],
        draft=view.package.draft or None,  # type: ignore[arg-type]
        draft_text=draft_text(view.package.draft) if view.package.draft else None,
        sitrep=SitrepOut.model_validate(view.sitrep, from_attributes=True) if view.sitrep else None,
    )


@router.get("/{advisory_no}", response_model=PackageOut)
def get_package(advisory_no: int, session: SessionDep, playbook: PlaybookDep) -> PackageOut:
    return _out(package_view(session, playbook, advisory_no))


@router.post("/{advisory_no}/items/{item_id}/decision", response_model=PackageOut)
def post_decision(
    advisory_no: int,
    item_id: int,
    body: DecisionIn,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
) -> PackageOut:
    """Approve or override a gap's action, or decide a conflict. Refusals change nothing."""
    decide(
        session,
        playbook,
        cycle,
        advisory_no,
        item_id,
        DecisionRequest(body.role, body.action, body.reason),
    )
    return _out(package_view(session, playbook, advisory_no))
