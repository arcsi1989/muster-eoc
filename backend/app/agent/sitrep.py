"""Approving the situation report (P-7.1): the commanding role edits and approves the draft.
The decision package lifecycle checks the approval; the advisory cycle's decision step applies
it, so its state write goes through the one path that records decisions."""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.advisory_context import SITREP_FLAG, Commander
from app.agent.decisions import DecisionRefused, Role, role_label
from app.audit.log import record
from app.errors import ConflictError, DataNotLoaded, NotFound
from app.models import Advisory, DecisionPackage, OpState, Sitrep
from app.playbook.service import Playbook, refresh_event_finding

SITREP_RULE = "P-7.1"


class SitrepAlreadyApproved(ConflictError):
    code = "sitrep_already_approved"


def draft_text(draft: dict[str, Any]) -> str:
    """The draft as editable plain text (headings, then paragraphs)."""
    blocks = []
    for section in draft.get("sections", []):
        blocks.append(section["heading"])
        blocks.extend(p["text"] for p in section["paragraphs"])
    return "\n\n".join(blocks)


def check_approval(
    session: Session, advisory_no: int, role: Role, text: str, lead: Commander
) -> None:
    """Raises unless `role` may approve `text` as the situation report for `advisory_no`, with
    `lead` the role that commands at the advisory."""
    package = session.get(DecisionPackage, advisory_no)
    if package is None or not package.draft:
        raise NotFound(f"no draft situation report for advisory {advisory_no}")
    if session.get(Sitrep, advisory_no) is not None:
        raise SitrepAlreadyApproved(f"the situation report for advisory {advisory_no} is approved")
    if role != lead:
        raise DecisionRefused(
            f"The {lead.replace('_', ' ')} approves the situation report (P-3.1, {SITREP_RULE})."
        )
    if not text.strip():
        raise DecisionRefused("The approved situation report cannot be empty.")


def apply_approval(
    session: Session, playbook: Playbook, advisory: Advisory, role: Role, text: str
) -> None:
    """Records the approved report, writes the per-advisory flag and re-evaluates P-7.1. Called
    only by the advisory cycle's decision step, after the lifecycle checked the approval."""
    package = session.get(DecisionPackage, advisory.advisory_no)
    if package is None:
        raise DataNotLoaded(f"no decision package for advisory {advisory.advisory_no}")
    now = datetime.now(UTC)
    edited = text.strip() != draft_text(package.draft).strip()
    session.add(
        Sitrep(
            advisory_no=advisory.advisory_no,
            approved_text=text.strip(),
            approved_by=role,
            approved_at=now,
            edited=edited,
        )
    )
    session.merge(OpState(entity="event", key=SITREP_FLAG, value=True, set_by=role, set_at=now))
    session.flush()
    refresh_event_finding(session, advisory, playbook, SITREP_RULE)
    record(
        session,
        "human",
        "sitrep_approved",
        f"{role_label(role)} approved the situation report"
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
