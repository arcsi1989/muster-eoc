"""The audit log: every system, agent and human step, with scenario time, an input hash and the
versions that produced it (plan section 4)."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from sqlmodel import Session, col, select

from app.models import Advisory, AuditEvent

Actor = Literal["system", "agent", "human"]


def input_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def record(
    session: Session,
    actor: Actor,
    event_type: str,
    summary: str,
    advisory: Advisory | None,
    payload: dict[str, Any],
    versions: dict[str, Any],
) -> AuditEvent:
    event = AuditEvent(
        recorded_at=datetime.now(UTC),
        advisory_no=advisory.advisory_no if advisory else None,
        hours_to_landfall=advisory.hours_to_landfall if advisory else None,
        actor=actor,
        type=event_type,
        summary=summary,
        payload=payload,
        input_hash=input_hash(payload),
        versions=versions,
    )
    session.add(event)
    return event


def events(session: Session, actor: Actor | None = None) -> list[AuditEvent]:
    """Every audited step, newest first, optionally for one actor."""
    query = select(AuditEvent).order_by(col(AuditEvent.id).desc())
    if actor:
        query = query.where(AuditEvent.actor == actor)
    return list(session.exec(query))
