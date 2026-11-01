# 42: Architecture decision records and an architecture diagram

**What to build:** A reviewer should grasp the design in five minutes. `docs/adr/` holds only ADR-0001 (LangGraph for the advisory cycle), although the important decisions are recorded as rows in `docs/decisions.md`. Write short ADRs (context, decision, consequences, alternatives rejected, links to the decisions rows and code) for the decisions that matter most: (1) the LLM never decides: deterministic rules, scores and state, the LLM narrates; (2) grounded generation: validate, retry, template fallback, one module for every LLM task; (3) data classification: restricted fields never reach the model; (4) rule-based evaluation with a gate, no LLM judge; (5) champion and challenger: shadow models and human-approved promotion; (6) human approval and the audit log as the only path to operational state. In `docs/architecture.md`, add a module diagram (Mermaid) of the backend packages and the frontend features with the seams between them, and the flow of one advisory (hazard, risk, rules, package, drafting, decisions), using the vocabulary of `GLOSSARY.md`. Keep them consistent with the code as it is after tickets 37 to 40. Do not change code.

**Blocked by:** 37 (the copilot shows its work), 39 (runtime number grounding), 40 (model comparison), 38 (customers-out and crew-demand forecast)

**Status:** ready-for-agent

- [ ] Six ADRs in `docs/adr/`, numbered after 0001, each with context, decision, consequences and rejected alternatives, linked from `docs/architecture.md`
- [ ] `docs/architecture.md` has a Mermaid module diagram and an advisory-flow diagram that match the code (every module named exists)
- [ ] README links the ADRs
- [ ] `./scripts/check.sh` passes
