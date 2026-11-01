# 30: CR-03 C3: agent tracing (backend)

**What to build:** Every advisory-cycle node and every copilot turn records a span: run ID, advisory, node, start, end, status, model, tokens in and out, estimated cost, retries, citation validation result. The code uses OpenTelemetry; spans export to a local `trace_span` table by default, and to an OTLP endpoint (Langfuse, Jaeger) only if `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so no new service is required. Instrument the graph nodes (thin calls into the lifecycle since ticket 15) and the grounded generation module (every attempt, retry, fallback and validation since tickets 16 and 17), not each caller. Prices live in `config/llm.yaml`; totals per advisory and per demo run (latency, tokens, cost). The audit log stays the record of what happened and who decided; traces are observability and do not duplicate it (choice recorded in `docs/decisions.md`). New dependencies `opentelemetry-api` and `opentelemetry-sdk` (OTLP exporter as an optional extra), justified in `docs/decisions.md`. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 15 (Graph nodes delegate to the lifecycle), 17 (Copilot through grounded generation)

**Status:** resolved

- [x] Span per cycle node and per copilot turn with the fields above, in `trace_span`; OTLP export only when the variable is set
- [x] Instrumentation in the graph nodes and the grounded generation module only
- [x] Prices in `config/llm.yaml`; endpoint for an advisory's trace with per-advisory and per-run totals
- [x] Tests: every advisory cycle produces a complete trace; a forced LLM failure shows the retry and the template fallback; template mode shows zero tokens and zero cost
- [x] `make demo-reset` clears traces with the rest of the scenario
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as bf141be after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
