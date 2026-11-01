# 29: CR-03 C1: live evaluation run

**What to build:** The evaluation runs against the real provider once, so the report shows real numbers: `make eval-llm` passes every gate with the shipped prompts, a deliberately broken prompt (citation instruction removed) fails the grounding gate, and the README links the latest `docs/eval/report.md`. Needs `ANTHROPIC_API_KEY` in the environment and costs API money, so a person runs it. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 28 (CR-03 C1: golden set and evaluation gate)

**Status:** resolved

- [x] `make eval-llm` with the shipped prompts passes every gate; report and results committed
- [x] With the citation instruction removed, `make eval-llm` fails the grounding gate (prompt restored afterwards)
- [x] README links the latest report

## Comments

- 2026-11-01: Run by a person's request with `claude-sonnet-5-5`, 3 repeats. Run 4 (copilot prompt v2, number-check fixes of ticket 35, drafts naming their cited IDs) passed every gate at 100%: grounding 36/36, refusal 18/18, classification 12/12, injection 12/12, drafting 12/12; it is `docs/eval/report.md`. With the citation instruction removed, grounding fell to 34/36 (94%) and failed its gate; the prompt was restored. Runs 1 to 3 and why each fix went where it did: `docs/decisions.md`.
