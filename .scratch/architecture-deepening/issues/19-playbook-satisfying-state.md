# 19: The playbook answers "what satisfies this finding"

**What to build:** The playbook module, not the action or package code, gives the proposed action for a finding, the state that would satisfy it (which may be several state keys together, as P-6.2 in v3.3, or none, as a P-2.5 proposal), and which findings become package items and how (leaving out the P-7.1 situation report rule; presenting P-2.5 as an activation proposal). The engine's predicate and detail-key formats stay internal. It also answers the two questions the field supervisor view (CR-02 C2, ticket 23) needs, so that ticket consumes them instead of re-deriving playbook rules: which approved items need field work and which state key completes each (`inspection_completed`, `barrier_installed`, `generator_assigned`, `relocated`), and whether a site is under the P-4.7 stop-work prohibition. Entity names are resolved in one place. Clause text and thresholds are not edited. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 15 (Graph nodes delegate to the lifecycle)

**Status:** resolved

- [x] Proposed action and approval state come from the playbook interface; action code no longer inverts predicates or reads detail keys
- [x] Package items for an advisory come from the playbook, which leaves out P-7.1 and presents P-2.5 as a proposal
- [x] Field work: the playbook says which approved items need field work, which state key completes each, and whether a site is under P-4.7 stop-work
- [x] One entity name lookup used by the package view, playbook views and the cycle
- [x] Seeded-session tests: satisfying state for a finding, including P-6.2's two keys and a proposal's none; P-7.1 left out of items; P-2.5 presented as a proposal; the field-work item and completing key for PS-14's P-4.2 inspection; PS-14 under P-4.7 stop-work at advisory 5
- [x] Package items and proposed actions in the demo unchanged; `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 93048f7 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
