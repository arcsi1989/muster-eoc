# 05: Decision package lifecycle: one answer to "is it open"

**What to build:** A decision package lifecycle module that is the only answer to "is the package for this advisory open" and through which item decisions pass. The package status the API returns is that answer; the frontend stops recomputing whether the situation report is open. Each item decision resolves the activation level once and runs the decision rule check once, before anything changes, so a refusal still changes nothing. The DB stays the record (ADR 0001); the checkpoint's waiting state is read only inside the lifecycle. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 02 (Advisory context module), CR-01 implemented (playbook v3.3)

**Status:** ready-for-agent

- [ ] Lifecycle module: open, read package view (open? who commands, from the declared level? activation proposal?), decide item; the only reader of the cycle's waiting state
- [ ] Item decisions go through it; level and rule check happen once per decision
- [ ] API package status comes from the lifecycle; frontend uses it instead of its own "situation report open" logic, with its test updated
- [ ] Seeded-session tests: decide → refusal changes nothing; decision on a closed or expired package refused; package status and waiting state never disagree; one audit record per decision
- [ ] End-to-end demo test green and not edited by this ticket; `./scripts/check.sh` passes
