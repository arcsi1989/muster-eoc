from fastapi import APIRouter

from muster.agent.lifecycle import draft_planning, release_planning
from muster.api.schemas import PlanningOut, PlanningReleaseIn
from muster.deps import CycleDep, LLMDep, PlaybookDep, ScoringConfigDep, SessionDep
from muster.models import PlanningDraft
from muster.planning import service as planning

router = APIRouter(prefix="/packages/{advisory_no}/planning")


def planning_out(draft: PlanningDraft) -> PlanningOut:
    return PlanningOut(
        **draft.products.model_dump(),
        advisory_no=draft.advisory_no,
        status=planning.status(draft),
        drafted_at=draft.drafted_at,
        planning_approved_at=draft.planning_approved_at,
        released_by=draft.released_by,
        released_at=draft.released_at,
    )


@router.get("", response_model=PlanningOut)
def get_planning(advisory_no: int, session: SessionDep) -> PlanningOut:
    """The ICS-215 and IAP objectives drafted for the period after the advisory."""
    return planning_out(planning.require_draft(session, advisory_no))


@router.post("/draft", response_model=PlanningOut)
def post_draft(
    advisory_no: int,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
    config: ScoringConfigDep,
    llm: LLMDep,
) -> PlanningOut:
    """Drafts (or redrafts, until the Planning Section Chief approves) the ICS-215 and IAP
    objectives from the package's approved items and open findings, while it is open."""
    return planning_out(draft_planning(session, playbook, cycle, config, llm, advisory_no))


@router.post("/release", response_model=PlanningOut)
def post_release(
    advisory_no: int,
    body: PlanningReleaseIn,
    session: SessionDep,
    playbook: PlaybookDep,
    cycle: CycleDep,
) -> PlanningOut:
    """The next release approval: the Planning Section Chief, then the commanding role.
    Refusals change nothing."""
    return planning_out(release_planning(session, playbook, cycle, advisory_no, body.role))
