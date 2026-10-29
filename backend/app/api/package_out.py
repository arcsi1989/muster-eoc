"""The decision package as the API serves it; shared by the package and activation routes."""

from app.agent.lifecycle import PackageView
from app.agent.sitrep import draft_text
from app.api.schemas import PackageItemOut, PackageOut, SitrepOut


def package_out(view: PackageView) -> PackageOut:
    return PackageOut(
        advisory_no=view.package.advisory_no,
        status=view.status,
        activation_level=view.activation_level,
        proposed_activation_level=view.proposed_activation_level,
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
