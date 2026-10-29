# 12: Direct tests for rule inputs, and one owner for re-evaluation

**What to build:** The rule-input builder (the namespace the playbook rules read) stays internal to the playbook module but is tested directly through the seeded session, so a field-name bug is caught without a replay. Re-evaluating one finding after a state change becomes part of the playbook interface, used by the lifecycle's state-writing path instead of a patch called from outside. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 01 (Seeded session test fixture), 06 (Situation report approval and activation declaration through the lifecycle)

**Status:** ready-for-agent

- [ ] Seeded-session tests for rule inputs at a seeded advisory: facilities an asset feeds, pumping stations in the top 25 that serve the treatment plant, proposed activation level, hours since Full was declared
- [ ] Re-evaluating one finding is a playbook operation; the lifecycle calls it; no external patch helper remains
- [ ] Test: after a state write, the re-evaluated finding changes status as expected
- [ ] HTTP replay tests that only covered rule inputs replaced, not kept alongside
- [ ] `./scripts/check.sh` passes
