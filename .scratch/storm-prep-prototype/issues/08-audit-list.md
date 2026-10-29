# 08: Audit list

**What to build:** An Incident Commander or auditor opens the Audit route and reconstructs what happened: every system, agent and human step in order, filterable by actor, with scenario and wall-clock time and the versions that produced it. Spec: `.scratch/storm-prep-prototype/spec.md`.

**Blocked by:** 06 (Advisory cycle and decisions by role)

**Status:** resolved

- [x] `GET /audit` with an optional actor filter (system, agent, human), newest first
- [x] Audit route listing each event: scenario time, wall-clock time, actor, type, summary; details expandable (input hash, model / rules / prompt versions, payload)
- [x] Human decisions show role, action and reason; "not decided" closures are visible
- [x] Loading, error and empty states
- [x] API test for the filter; frontend tests for the list states
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Resolved with ht-resolve: built in the step 1-10 commits (8a14132 to ac188e6, 102309d); user confirmed 2026-10-29.
