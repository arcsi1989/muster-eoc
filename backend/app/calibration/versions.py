"""Model versions: the fragility curves and the challenger risk scoring can use. The champion,
which ranks, is the latest approved version of either kind; a proposed version is used only once
a person approves it (L6, B10). A challenger in shadow cannot be approved: it is proposed only
when it passes the promotion rule (app.challenger.promotion)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app import advisory_context
from app.agent.decisions import DecisionRefused, Role, role_label
from app.audit.log import record
from app.errors import ConflictError, DataNotLoaded, NotFound
from app.models import Advisory, FragilityCurve, ModelVersion, ModelVersionKind

APPROVERS: tuple[Role, ...] = ("planning", "director", "incident_commander")
APPROVED_EVENT = "model_version_approved"


class AlreadyApproved(ConflictError):
    code = "already_approved"


class NotProposed(ConflictError):
    code = "not_proposed"


@dataclass(frozen=True)
class ActiveModelVersion:
    id: int
    label: str
    curves: list[FragilityCurve]


def all_versions(session: Session) -> list[ModelVersion]:
    return list(session.exec(select(ModelVersion).order_by(col(ModelVersion.id))))


def _latest_approved(session: Session, kind: ModelVersionKind | None = None) -> ModelVersion:
    query = select(ModelVersion).where(ModelVersion.status == "approved")
    if kind is not None:
        query = query.where(ModelVersion.kind == kind)
    query = query.order_by(col(ModelVersion.approved_at).desc(), col(ModelVersion.id).desc())
    version = session.exec(query).first()
    if version is None or version.id is None:
        raise DataNotLoaded("no approved model version; the gold data was not loaded")
    return version


def in_use(session: Session) -> ActiveModelVersion:
    """The latest approved fragility curves: the rule-based score of the next advisory, and its
    p_fail too while the rules are the champion."""
    version = _latest_approved(session, "curves")
    return ActiveModelVersion(version.id or 0, version.label, curves(version))


def champion(session: Session) -> ModelVersion:
    """The latest approved version of either kind: the one the next advisory is ranked with."""
    return _latest_approved(session)


def curves(version: ModelVersion) -> list[FragilityCurve]:
    return [FragilityCurve(**c) for c in version.curves]


def approve(session: Session, version_id: int, role: Role) -> ModelVersion:
    """A person approves a proposed version; scoring uses it from the next advisory on. Planning
    maintains the risk list (P-3.3), the Director or Incident Commander commands."""
    version = session.get(ModelVersion, version_id)
    if version is None:
        raise NotFound(f"model version {version_id} does not exist")
    if role not in APPROVERS:
        raise DecisionRefused(
            "A model version is approved by Planning, the Director or the Incident Commander."
        )
    if version.status == "approved":
        raise AlreadyApproved(f"model version {version_id} is already approved")
    if version.status != "proposed":
        raise NotProposed(
            f"model version {version_id} is in shadow: only a proposed version can be approved"
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
        f"{role_label(role)} approved model version {version_id} "
        f"({version.label}); scoring uses it from the next advisory",
        session.get(Advisory, current) if current else None,
        {"model_version": version_id, "approved_by": role, "curves": version.curves},
        {"model_version": version_id},
    )
    session.commit()
    session.refresh(version)
    return version
