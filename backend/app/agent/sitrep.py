"""Approving the situation report (P-7.1): the commanding role edits and approves the draft."""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.agent.decisions import DecisionRefused, Role, commander
from app.audit.log import record
from app.errors import ConflictError, NotFound
from app.models import DecisionPackage, OpState, Sitrep
from app.playbook.activation import activation_level
from app.playbook.service import Playbook, refresh_event_finding
from app.replay import service

SITREP_RULE = "P-7.1"
SITREP_FLAG = "sitrep_approved_current"


class SitrepAlreadyApproved(ConflictError):
    code = "sitrep_already_approved"


def draft_text(draft: dict[str, Any]) -> str:
    """The draft as editable plain text (headings, then paragraphs)."""
    blocks = []
    for section in draft.get("sections", []):
        blocks.append(section["heading"])
        blocks.extend(p["text"] for p in section["paragraphs"])
    return "\n\n".join(blocks)


def approve_sitrep(
    session: Session, playbook: Playbook, advisory_no: int, role: Role, text: str
) -> Sitrep:
    advisory = service.require_issued(session, advisory_no)
    if advisory_no != service.current_advisory(session):
        raise ConflictError(f"advisory {advisory_no} is no longer current")
    package = session.get(DecisionPackage, advisory_no)
    if package is None or not package.draft:
        raise NotFound(f"no draft situation report for advisory {advisory_no}")
    if session.get(Sitrep, advisory_no) is not None:
        raise SitrepAlreadyApproved(f"the situation report for advisory {advisory_no} is approved")
    lead = commander(activation_level(advisory.hours_to_landfall, playbook.levels) == "full")
    if role != lead:
        raise DecisionRefused(
            f"The {lead.replace('_', ' ')} approves the situation report (P-3.1, P-7.1)."
        )
    if not text.strip():
        raise DecisionRefused("The approved situation report cannot be empty.")

    now = datetime.now(UTC)
    edited = text.strip() != draft_text(package.draft).strip()
    sitrep = Sitrep(
        advisory_no=advisory_no,
        approved_text=text.strip(),
        approved_by=role,
        approved_at=now,
        edited=edited,
    )
    session.add(sitrep)
    session.merge(OpState(entity="event", key=SITREP_FLAG, value=True, set_by=role, set_at=now))
    session.flush()
    refresh_event_finding(session, advisory, playbook, SITREP_RULE)
    record(
        session,
        "human",
        "sitrep_approved",
        f"{role.replace('_', ' ').capitalize()} approved the situation report"
        + (" after editing the draft" if edited else " as drafted"),
        advisory,
        {
            "role": role,
            "edited": edited,
            "draft_provider": package.draft.get("provider"),
            "state_written": {f"event.{SITREP_FLAG}": True},
        },
        {"prompt_version": package.draft.get("prompt_version")},
    )
    session.commit()
    return sitrep
