# 42: Brief deliverables: architecture, assumptions and limitations, sample data, ADRs

**What to build:** A reviewer should grasp the design in five minutes. `docs/adr/` holds only ADR-0001 (LangGraph for the advisory cycle), although the important decisions are recorded as rows in `docs/decisions.md`. Write short ADRs (context, decision, consequences, alternatives rejected, links to the decisions rows and code) for the decisions that matter most: (1) the LLM never decides: deterministic rules, scores and state, the LLM narrates; (2) grounded generation: validate, retry, template fallback, one module for every LLM task; (3) data classification: restricted fields never reach the model; (4) rule-based evaluation with a gate, no LLM judge; (5) champion and challenger: shadow models and human-approved promotion; (6) human approval and the audit log as the only path to operational state. In `docs/architecture.md`, add a module diagram (Mermaid) of the backend packages and the frontend features with the seams between them, and the flow of one advisory (hazard, risk, rules, package, drafting, decisions), using the vocabulary of `GLOSSARY.md`. Keep them consistent with the code as it is after tickets 36 to 41.

The brief asks for a README with setup and run instructions, a written description of the architecture, assumptions and limitations, and the sample or mocked data used in the demo. Bring all three up to date with the code: (a) rewrite `docs/architecture.md` around the diagrams so it describes the system as built (CR-01 to CR-03 and tickets 36 to 41: storm map and districts, field tasks, ICS-215 and IAP, calibration, champion and challenger, tracing, the copilot dock and its progress stream, runtime number grounding, the evaluation and model comparison, CI); (b) revise `docs/assumptions_limitations.md` so every statement is true today (for example, copilot numbers are now checked at runtime, ticket 39) and add what the later work assumes (model comparison prompts tuned on Sonnet, synthetic history); (c) add a README section "Sample data" listing every committed data file (`data/gold/`, `data/history/`, `data/models/`, `data/playbook/`), what it holds, that it is synthetic and how it is regenerated (`make data`, `make history`, `make train`); (d) fix stale README figures (the `make eval-compare` cost estimate: measured $4.68 for the three defaults, `docs/eval/comparison.md`). Do not change code.

**Blocked by:** 37 (the copilot shows its work), 39 (runtime number grounding), 40 (model comparison), 38 (customers-out and crew-demand forecast)

**Status:** resolved

- [x] Six ADRs in `docs/adr/`, numbered after 0001, each with context, decision, consequences and rejected alternatives, linked from `docs/architecture.md`
- [x] `docs/architecture.md` has a Mermaid module diagram and an advisory-flow diagram that match the code (every module named exists)
- [x] README links the ADRs
- [x] `docs/architecture.md` and `docs/assumptions_limitations.md` describe the code as it is: no statement contradicted by the code (for example runtime number grounding)
- [x] README "Sample data" section lists every committed data file, what it is, that it is synthetic, and how it is regenerated; stale figures fixed
- [x] `./scripts/check.sh` passes

## Comments

- 2026-11-01: Merged into `main` as 1d0196d after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
