"""Model versions: the fragility curves risk scoring uses. Scoring always uses the latest
approved version; a proposed version is used only once a person approves it (L6, B10)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app import advisory_context
from app.agent.decisions import DecisionRefused, Role
from app.audit.log import record
from app.errors import ConflictError, DataNotLoaded, NotFound
from app.models import Advisory, FragilityCurve, ModelVersion

APPROVERS: tuple[Role, ...] = ("planning", "director", "incident_commander")
APPROVED_EVENT = "model_version_approved"


class AlreadyApproved(ConflictError):
    code = "already_approved"


@dataclass(frozen=True)
class InUse:
    id: int
    label: str
    curves: list[FragilityCurve]


def all_versions(session: Session) -> list[ModelVersion]:
    return list(session.exec(select(ModelVersion).order_by(col(ModelVersion.id))))


def in_use(session: Session) -> InUse:
    """The latest approved version: the one the next advisory is scored with."""
    query = (
        select(ModelVersion)
        .where(ModelVersion.status == "approved")
        .order_by(col(ModelVersion.approved_at).desc(), col(ModelVersion.id).desc())
    )
    version = session.exec(query).first()
    if version is None or version.id is None:
        raise DataNotLoaded("no approved model version; the gold data was not loaded")
    return InUse(version.id, version.label, curves(version))


def curves(version: ModelVersion) -> list[FragilityCurve]:
    return [FragilityCurve(**c) for c in version.curves]


def approve(session: Session, version_id: int, role: Role) -> ModelVersion:
    """A person approves a proposed version; scoring uses it from the next advisory on. Planning
    maintains the risk list (P-3.3), the Director or Incident Commander commands."""
    version = session.get(ModelVersion, version_id)
    if version is None:
        raise NotFound(f"model version {version_id} does not exist")
    if version.status == "approved":
        raise AlreadyApproved(f"model version {version_id} is already approved")
    if role not in APPROVERS:
        raise DecisionRefused(
            "A model version is approved by Planning, the Director or the Incident Commander."
        )
    version.status = "approved"
    version.approved_by = role
    version.approved_at = datetime.now(UTC)
    session.add(version)
    current = advisory_context.current_advisory_no(session)
    record(
        session,
        "human",
        APPROVED_EVENT,
        f"{role.replace('_', ' ').capitalize()} approved model version {version_id} "
        f"({version.label}); scoring uses it from the next advisory",
        session.get(Advisory, current) if current else None,
        {"model_version": version_id, "approved_by": role, "curves": version.curves},
        {"model_version": version_id},
    )
    session.commit()
    session.refresh(version)
    return version
