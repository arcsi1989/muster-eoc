# 31: CR-03 C3: run trace panel

**What to build:** A "Run trace" panel per advisory shows what the agent did: the cycle nodes and copilot turns as a waterfall of duration bars, with model, tokens and cost per span, any retry or fallback to the template draft highlighted, and totals for the advisory and the demo run. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 30 (CR-03 C3: agent tracing (backend))

**Status:** ready-for-agent

- [ ] Panel reachable per advisory; waterfall of spans with duration bars
- [ ] Tokens, cost and model per span; retries and template fallbacks highlighted
- [ ] Totals per advisory and per run
- [ ] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [ ] Frontend tests for the waterfall, the highlights and the totals
- [ ] `./scripts/check.sh` passes
