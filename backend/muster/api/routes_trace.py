from dataclasses import asdict

from fastapi import APIRouter

from muster.api.schemas import RunTraceOut, TraceSpanOut, TraceTotalsOut
from muster.deps import SessionDep
from muster.replay import service
from muster.tracing.store import run_trace

router = APIRouter(prefix="/advisories")


@router.get("/{advisory_no}/trace", response_model=RunTraceOut)
def get_trace(advisory_no: int, session: SessionDep) -> RunTraceOut:
    """What the agent did for an issued advisory: its cycle nodes and generations as spans, with
    latency, tokens and estimated cost for the advisory and for the demo run."""
    service.require_issued(session, advisory_no)
    trace = run_trace(session, advisory_no)
    return RunTraceOut(
        run_id=trace.run_id,
        advisory_no=advisory_no,
        spans=[TraceSpanOut.model_validate(s, from_attributes=True) for s in trace.spans],
        advisory_totals=TraceTotalsOut(**asdict(trace.advisory_totals)),
        run_totals=TraceTotalsOut(**asdict(trace.run_totals)),
    )
