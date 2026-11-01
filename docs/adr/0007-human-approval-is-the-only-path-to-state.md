# Human approval and the audit log are the only path to operational state

Status: accepted, 2026-10-28 (the brief's hard rule); one path for every kind of decision since
tickets 13–15 (2026-10-29), extended to field reports and planning release by CR-02.

## Context

"The prototype prepares; it never acts." Operational state (generators fuelled, inspections done,
the activation level, the situation report approved) decides which gaps the playbook reports next.
Many things want to change it: item approvals and overrides, conflict decisions, activation
declarations, situation report approval, field supervisors' done and blocked reports, the release
of the ICS-215 and IAP. If each wrote state its own way, a refusal could leave half a change behind
and the audit log could miss a write.

## Decision

- Every decision is **checked** by the decision package lifecycle (`backend/muster/agent/lifecycle.py`)
  under the advisory cycle's lock, before anything changes: the package is open, the role may take
  this decision (`agent/decisions.py`: the owner role or the commanding role approves, only the
  commanding role overrides with a reason, only the Incident Commander decides conflicts), the
  field task is in the supervisor's district and not under stop-work. A refusal changes nothing.
- Every accepted decision is **applied** by one step, the advisory cycle's `apply_decision` node
  (`CycleSteps.apply`), resumed through LangGraph's interrupt
  ([ADR 0001](0001-langgraph-for-the-advisory-cycle.md)). It writes the state, re-evaluates the
  affected finding through the playbook and records the audit event in the same transaction.
- Besides that step, only the initial load, a scenario reset and the per-advisory flag reset when an
  advisory is issued write operational state. A declaration is the only code that sets the
  activation level.
- The **audit log** (`audit/log.py`) records every system, agent, human and field-supervisor step
  with scenario time, an input hash and the versions (rules, model, prompt) that produced it.
  Traces (`tracing/`) are observability only; nothing reads a span to decide anything.

## Consequences

- One place to reason about who may change what, and one record of it; the Audit page filters by
  actor.
- Approval counts the action as done from that moment; a field supervisor's Done confirms it and
  Blocked retracts it, both through the same step, so the gap returns in the next package.
- Advancing never waits: undecided items close as not decided and are audited as such.
- There is no authentication: the role selector and the field supervisor's district are the
  caller's word. The backend enforces what each role may decide, not who the person is.

## Alternatives rejected

- **Each route writes its own state.** Simpler at first, but the checks and audit events drifted
  apart; tickets 13–15 moved every decision onto one path.
- **The copilot or the draft proposing state changes that apply on a click.** Still a model
  initiating an operational change; the copilot's tools are read-only and it declines change
  requests.
- **The audit log as a side effect of tracing.** Spans are observability: they may be exported to
  another service or dropped, and they are not written in the transaction that changes state; the
  decision record must be in the same transaction as the state it explains.

## Links

- `docs/decisions.md`: 2026-10-28 approval counts as done, roles, no auth; 2026-10-29 package
  lifecycle, situation report approval, graph nodes delegate to the lifecycle (tickets 13–15),
  re-evaluation (ticket 20), declared activation (ticket 06); 2026-10-30 field tasks (ticket 23),
  ICS-215 and IAP release (ticket 25), tracing (ticket 30).
- Code: `agent/lifecycle.py`, `agent/graph.py`, `agent/cycle.py`, `agent/decisions.py`,
  `agent/field.py`, `agent/sitrep.py`, `playbook/service.py`, `audit/log.py`.
