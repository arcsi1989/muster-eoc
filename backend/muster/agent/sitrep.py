"""Approving the situation report (P-7.1): the commanding role edits and approves the draft.
The decision package lifecycle checks the approval; the advisory cycle's decision step applies
it, so its state write goes through the one path that records decisions, and re-evaluates
P-7.1 through the playbook."""

from datetime import UTC, datetime

from sqlmodel import Session

from muster.advisory_context import SITREP_FLAG, Commander
from muster.agent.decisions import DecisionRefused, Role, role_label
from muster.audit.log import record
from muster.errors import ConflictError, NotFound
from muster.llm.schemas import PackageDraft
from muster.models import Advisory, DecisionPackage, OpState, Sitrep
from muster.playbook.package import SITREP_RULE


class SitrepAlreadyApproved(ConflictError):
    code = "sitrep_already_approved"


def _draft(session: Session, advisory_no: int) -> PackageDraft:
    package = session.get(DecisionPackage, advisory_no)
    if package is None or package.draft is None:
        raise NotFound(f"no draft situation report for advisory {advisory_no}")
    return package.draft


def check_approval(
    session: Session, advisory_no: int, role: Role, text: str, lead: Commander
) -> None:
    """Raises unless `role` may approve `text` as the situation report for `advisory_no`, with
    `lead` the role that commands at the advisory."""
    _draft(session, advisory_no)
    if session.get(Sitrep, advisory_no) is not None:
        raise SitrepAlreadyApproved(f"the situation report for advisory {advisory_no} is approved")
    if role != lead:
        raise DecisionRefused(
            f"The {lead.replace('_', ' ')} approves the situation report (P-3.1, {SITREP_RULE})."
        )
    if not text.strip():
        raise DecisionRefused("The approved situation report cannot be empty.")


def apply_approval(session: Session, advisory: Advisory, role: Role, text: str) -> None:
    """Records the approved report and writes the per-advisory flag. Called only by the advisory
    cycle's decision step, after the lifecycle checked the approval; that step re-evaluates
    P-7.1."""
    draft = _draft(session, advisory.advisory_no)
    now = datetime.now(UTC)
    edited = text.strip() != draft.text().strip()
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
            "draft_provider": draft.provider,
            "state_written": {f"event.{SITREP_FLAG}": True},
        },
        {"prompt_version": draft.prompt_version},
    )
