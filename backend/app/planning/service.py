"""Drafting and releasing the planning products of the next operational period (CR-02 C3).

The decision package lifecycle gates both: a draft is written while the advisory's package is
open, and the release approvals are decisions it checks before the advisory cycle's decision
step applies them. Release takes two approvals in order: the Planning Section Chief, then the
role that commands at the advisory (the Incident Commander at Full activation)."""

from datetime import UTC, datetime

from sqlmodel import Session, delete, select

from app.advisory_context import Commander
from app.agent.decisions import DecisionRefused, Role, role_label
from app.audit.log import record
from app.errors import ConflictError, NotFound
from app.llm.provider import LLMProvider
from app.llm.schemas import ObjectivesRequest
from app.models import Advisory, Finding, PlanningDraft
from app.planning.ics215 import period_start_hours, worksheet
from app.planning.objectives import objectives, objectives_prompt, reword, worded
from app.planning.products import PlanningProducts, PlanningStatus
from app.playbook.service import Playbook
from app.scoring_config import PlanningConfig

PLANNING_CHIEF: Role = "planning"


class PlanningReleased(ConflictError):
    code = "planning_released"


class PlanningInRelease(ConflictError):
    """The Planning Section Chief approved the draft; redrafting would change what they
    approved."""

    code = "planning_in_release"


def status(draft: PlanningDraft) -> PlanningStatus:
    return "released" if draft.released_at else "DRAFT"


def require_draft(session: Session, advisory_no: int) -> PlanningDraft:
    draft = session.get(PlanningDraft, advisory_no)
    if draft is None:
        raise NotFound(f"no planning draft for advisory {advisory_no}")
    return draft


def _require_unreleased(draft: PlanningDraft) -> None:
    if draft.released_at:
        raise PlanningReleased(f"the planning draft for advisory {draft.advisory_no} is released")


def check_redraft(session: Session, advisory_no: int) -> None:
    """Raises if the advisory's planning draft is in release or released."""
    draft = session.get(PlanningDraft, advisory_no)
    if draft is None:
        return
    _require_unreleased(draft)
    if draft.planning_approved_at:
        raise PlanningInRelease(
            f"the Planning Section Chief approved the draft for advisory {advisory_no}; "
            "it is no longer redrafted"
        )


def draft(
    session: Session,
    advisory: Advisory,
    playbook: Playbook,
    config: PlanningConfig,
    llm: LLMProvider,
    fallback: LLMProvider,
) -> PlanningDraft:
    """Drafts the ICS-215 and the IAP objectives for the period after `advisory` and stores
    them as DRAFT, replacing an earlier draft. The rows and objectives are deterministic; the
    provider may only reword the objectives."""
    start = period_start_hours(advisory, config)
    findings = session.exec(select(Finding).where(Finding.advisory_no == advisory.advisory_no))
    request = ObjectivesRequest(advisory.advisory_no, objectives(list(findings), start))
    outcome = reword(llm, fallback, objectives_prompt(config), request, 1 + config.retries)
    products = PlanningProducts(
        period_start_hours=start,
        period_end_hours=start - config.period_hours,
        ics215=worksheet(session, advisory, playbook, config),
        objectives=worded(request, outcome),
        provider=outcome.provider,
        fallback=outcome.fallback,
        model=outcome.result.model,
        prompt_version=outcome.prompt_version,
        fallback_reason=outcome.fallback_reason,
    )
    stored = session.merge(
        PlanningDraft(
            advisory_no=advisory.advisory_no, products=products, drafted_at=datetime.now(UTC)
        )
    )
    record(
        session,
        "agent",
        "planning_drafted",
        f"Draft ICS-215 ({len(products.ics215)} assignments) and {len(products.objectives)} IAP "
        f"objectives for T-{start} to T-{products.period_end_hours}, objectives worded by "
        f"{outcome.provider}"
        + (f" ({outcome.fallback_reason})" if outcome.fallback_reason else ""),
        advisory,
        {
            "item_ids": [r.item_id for r in products.ics215],
            "need": sum(r.need for r in products.ics215),
            "objective_clauses": [o.clause_ids for o in products.objectives],
            "provider": outcome.provider,
            "model": outcome.result.model,
            "attempts": outcome.attempts,
            "fallback_reason": outcome.fallback_reason,
        },
        {"rules_version": playbook.rulebook.version, "prompt_version": outcome.prompt_version},
    )
    return stored


def check_release(session: Session, advisory_no: int, role: Role, lead: Commander) -> None:
    """Raises unless `role` gives the next release approval of the advisory's planning draft:
    the Planning Section Chief first, then `lead`, the role that commands at the advisory."""
    planning = require_draft(session, advisory_no)
    _require_unreleased(planning)
    commander = role_label(lead)
    if planning.planning_approved_at is None and role != PLANNING_CHIEF:
        raise DecisionRefused(
            "The Planning Section Chief approves the planning draft first, then the "
            f"{commander.lower()} releases it."
        )
    if planning.planning_approved_at is not None and role != lead:
        raise DecisionRefused(
            f"The {commander.lower()} releases the planning draft the Planning Section Chief "
            "approved."
        )


def apply_release(session: Session, advisory: Advisory, role: Role) -> None:
    """Records the next release approval. Called only by the advisory cycle's decision step,
    after the lifecycle checked it."""
    planning = require_draft(session, advisory.advisory_no)
    now = datetime.now(UTC)
    if planning.planning_approved_at is None:
        planning.planning_approved_at = now
        event, summary = "planning_approved", "Planning Section Chief approved the planning draft"
    else:
        planning.released_by, planning.released_at = role, now
        event = "planning_released"
        summary = f"{role_label(role)} released the ICS-215 and IAP objectives"
    session.add(planning)
    record(
        session, "human", event, summary, advisory, {"role": role, "status": status(planning)}, {}
    )


def clear(session: Session) -> None:
    """Deletes every planning draft (scenario reset)."""
    session.exec(delete(PlanningDraft))
