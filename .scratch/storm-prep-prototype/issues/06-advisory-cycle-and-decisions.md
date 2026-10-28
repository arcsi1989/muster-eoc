# 06: Advisory cycle and decisions by role

**What to build:** Each advisory runs the advisory cycle and pauses for people. An operator picks a role in the header and approves, overrides or decides each item in the decision package; approvals change the state the next advisory sees; conflicts can only be decided by the Incident Commander; advancing closes undecided items. The scripted demo works end to end in template mode. Spec: `.scratch/storm-prep-prototype/spec.md`; ADR 0001 (LangGraph); decision log for the state mapping and permissions.

**Blocked by:** 05 (Playbook rule engine and findings)

**Status:** ready-for-agent

- [ ] A LangGraph cycle per advisory: load context → diff → evaluate rules → draft (template text for now) → await approval ⇄ apply decision → finalise; one thread per advisory; the checkpointer uses its own SQLite file, deleted by reset
- [ ] Each decision resumes the paused thread; only the deterministic apply-decision node writes state; the graph loops until no items remain; advancing resumes the previous thread once with "expire", closing undecided items as "not decided"
- [ ] Role selector in the header (Incident Commander shown as Director below Full activation, Planning, Operations, Logistics, Regulatory Liaison), recorded as decided by
- [ ] Permissions: approve by owner role or Incident Commander/Director; override (reason required) only by Incident Commander/Director; conflict only by the Incident Commander with outcomes "Defer" or "Alternative measure" plus reason, neither setting the blocked action's state; refusals return the standard error body and change nothing
- [ ] Approval sets every `satisfied_if` key true; P-4.3 sets fuelled generators to the required count; P-4.1 is a Planning item; per-advisory flags reset each advisory, other state carries over; the UI states that approval counts the action as done
- [ ] `GET /packages/{advisory}` and `POST /packages/{advisory}/items/{item_id}/decision`; decision package UI with "What changed", gaps with proposed actions, and "Conflicts (Incident Commander decides)"
- [ ] Every node and decision writes an audit event (actor, scenario and wall-clock time, input hash, versions)
- [ ] API test of the plan's section 8 scenario on both paths: PS-14 overridden at advisory 3 → conflict citing P-4.2, P-4.7 and P-8.2 at advisory 5 decided by the Incident Commander; PS-14 inspected at advisory 3 → no conflict at 5; plus every row of the section 8 table and each role refusal
- [ ] `./scripts/check.sh` passes
