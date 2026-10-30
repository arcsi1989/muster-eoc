from fastapi import APIRouter

from muster.api.schemas import AuditEventOut
from muster.audit.log import Actor, events
from muster.deps import SessionDep

router = APIRouter()


@router.get("/audit", response_model=list[AuditEventOut])
def list_audit(session: SessionDep, actor: Actor | None = None) -> list[AuditEventOut]:
    """Every audited step, newest first, optionally for one actor."""
    return [AuditEventOut.model_validate(e, from_attributes=True) for e in events(session, actor)]
