# 05: Playbook rule engine and findings

**What to build:** On each advisory the playbook rules are evaluated deterministically for every relevant entity. The operator opens the Decision package tab and sees, read-only, the gaps (with clause ID, entity and owner role), the conflicts where stop-work blocks field work, and the satisfied findings collapsed. Spec: `.scratch/storm-prep-prototype/spec.md`; semantics at the top of the playbook rules file; glossary terms finding, gap, conflict, prohibition.

**Blocked by:** 04 (Risk score, explanation and alerts)

**Status:** resolved

- [x] The playbook is parsed into clauses (ID, section, text); all 29 clause IDs available
- [x] The rule engine implements: active-from hours; `when` and `satisfied_if` predicates with every operator (eq, ne, gt, ge, lt, le, in, contains_any, is_true, is_false), including `value_field`; the evaluation context fields from the plan's section 2.4 (including transitive `feeds_facility_types` and `critical_feeding_assets_top25`)
- [x] Deadlines: P-7.2 overdue when hours since Full activation (48 − hours to landfall) exceeds 12, escalating severity to critical
- [x] Prohibitions never become findings on their own; they turn any open rule with field work on the same entity into a conflict citing both clauses and P-8.2
- [x] Findings stored per rule × entity × advisory with status satisfied / open / conflict, severity, owner role and details; computed on advance against the current state
- [x] The rules file and the playbook text are not edited
- [x] Decision package tab lists gaps and conflicts with clause and entity IDs (no decisions yet)
- [x] Engine unit tests cover every rule in the rules file, plus prohibition blocking and deadline escalation
- [x] Section 8 rows that need only data and the engine pass (with initial state: advisory 1 opens P-4.1, P-4.3, P-7.1; advisory 3 opens P-4.5 for SUB-07 and P-4.2 for PS-14; advisory 4 opens P-4.6 for STG-02; advisory 5 gives the PS-14 conflict)
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Resolved with ht-resolve: built in the step 1-10 commits (8a14132 to ac188e6, 102309d); user confirmed 2026-10-29.
