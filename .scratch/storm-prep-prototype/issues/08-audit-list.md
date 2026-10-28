# 08: Audit list

**What to build:** An Incident Commander or auditor opens the Audit route and reconstructs what happened: every system, agent and human step in order, filterable by actor, with scenario and wall-clock time and the versions that produced it. Spec: `.scratch/storm-prep-prototype/spec.md`.

**Blocked by:** 06 (Advisory cycle and decisions by role)

**Status:** ready-for-agent

- [ ] `GET /audit` with an optional actor filter (system, agent, human), newest first
- [ ] Audit route listing each event: scenario time, wall-clock time, actor, type, summary; details expandable (input hash, model / rules / prompt versions, payload)
- [ ] Human decisions show role, action and reason; "not decided" closures are visible
- [ ] Loading, error and empty states
- [ ] API test for the filter; frontend tests for the list states
- [ ] `./scripts/check.sh` passes
