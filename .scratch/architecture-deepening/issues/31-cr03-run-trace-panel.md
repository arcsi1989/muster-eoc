# 31: CR-03 C3: run trace panel

**What to build:** A "Run trace" panel per advisory shows what the agent did: the cycle nodes and copilot turns as a waterfall of duration bars, with model, tokens and cost per span, any retry or fallback to the template draft highlighted, and totals for the advisory and the demo run. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 30 (CR-03 C3: agent tracing (backend))

**Status:** resolved

- [x] Panel reachable per advisory; waterfall of spans with duration bars
- [x] Tokens, cost and model per span; retries and template fallbacks highlighted
- [x] Totals per advisory and per run
- [x] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [x] Frontend tests for the waterfall, the highlights and the totals
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 4ad8b51 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
