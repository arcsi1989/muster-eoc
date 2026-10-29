# 15: Graph nodes delegate to the lifecycle

**What to build:** The LangGraph advisory cycle keeps only orchestration: the order of steps and the pause for decisions (ADR 0001, not reopened). The node bodies (creating package items, saving the draft, expiring, closing, writing audit records) move into the decision package lifecycle module, and the nodes call it. The P-7.1 rule ID, the situation report flag and the item status values are each defined once; the API item status reuses the backend definition. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 14 (Situation report approval and activation declaration through the lifecycle)

**Status:** ready-for-agent

- [ ] Each graph node is a short call into the lifecycle; no table queries or audit summaries written in the graph
- [ ] P-7.1 rule ID, situation report flag, item status values defined once each
- [ ] Seeded-session test of the full lifecycle without running HTTP: open → declare the proposed level → decide → approve situation report → close, with a fake provider
- [ ] Audit event types and summaries unchanged
- [ ] If moving the bodies only shifts code without concentrating it (deletion test fails), stop and propose a smaller change in Comments
- [ ] End-to-end demo test green and not edited by this ticket; `./scripts/check.sh` passes
