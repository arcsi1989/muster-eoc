"""A model version as the API serves it; shared by the calibration and challenger routes."""

from sqlmodel import Session

from app.api.schemas import CurveOut, ModelVersionOut
from app.calibration import versions
from app.models import ModelVersion


def version_out(session: Session, version: ModelVersion) -> ModelVersionOut:
    return ModelVersionOut(
        id=version.id or 0,
        label=version.label,
        kind=version.kind,
        status=version.status,
        in_use=version.id == versions.champion(session).id,
        curves=[CurveOut.model_validate(c) for c in version.curves],
        created_at=version.created_at,
        approved_by=version.approved_by,
        approved_at=version.approved_at,
    )
