# 29: CR-03 C1: live evaluation run

**What to build:** The evaluation runs against the real provider once, so the report shows real numbers: `make eval-llm` passes every gate with the shipped prompts, a deliberately broken prompt (citation instruction removed) fails the grounding gate, and the README links the latest `docs/eval/report.md`. Needs `ANTHROPIC_API_KEY` in the environment and costs API money, so a person runs it. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 28 (CR-03 C1: golden set and evaluation gate)

**Status:** ready-for-human

- [ ] `make eval-llm` with the shipped prompts passes every gate; report and results committed
- [ ] With the citation instruction removed, `make eval-llm` fails the grounding gate (prompt restored afterwards)
- [ ] README links the latest report
