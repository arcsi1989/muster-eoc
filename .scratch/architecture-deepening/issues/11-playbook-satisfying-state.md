# 11: The playbook answers "what satisfies this finding"

**What to build:** The playbook module, not the action or package code, gives the proposed action for a finding, the state that would satisfy it, and which findings become package items (leaving out the P-7.1 situation report rule). The engine's predicate and detail-key formats stay internal. Entity names are resolved in one place. Clause text and thresholds are not edited. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 07 (Graph nodes delegate to the lifecycle)

**Status:** ready-for-agent

- [ ] Proposed action and approval state come from the playbook interface; action code no longer inverts predicates or reads detail keys
- [ ] Package items for an advisory come from the playbook, which leaves out P-7.1
- [ ] One entity name lookup used by the package view, playbook views and the cycle
- [ ] Seeded-session tests: satisfying state for a finding; P-7.1 left out of items
- [ ] Package items and proposed actions in the demo unchanged; `./scripts/check.sh` passes
