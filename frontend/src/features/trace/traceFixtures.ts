import type { RunTrace, TraceSpan, TraceTotals } from '../../types/scenario'

const T0 = Date.parse('2026-10-30T09:00:00Z')

/** A span starting `startMs` after 09:00 and lasting `durationMs`. */
export const makeSpan = (
  overrides: Partial<TraceSpan> & Pick<TraceSpan, 'span_id' | 'node'>,
  startMs = 0,
  durationMs = 100,
): TraceSpan => ({
  parent_span_id: null,
  advisory_no: 3,
  kind: 'cycle_node',
  started_at: new Date(T0 + startMs).toISOString(),
  ended_at: new Date(T0 + startMs + durationMs).toISOString(),
  duration_ms: durationMs,
  status: 'ok',
  provider: null,
  model: null,
  tokens_in: 0,
  tokens_out: 0,
  cost_usd: 0,
  retries: 0,
  fallback: false,
  fallback_reason: null,
  validation: null,
  attempts: [],
  ...overrides,
})

export const makeTotals = (overrides: Partial<TraceTotals> = {}): TraceTotals => ({
  latency_ms: 0,
  tokens_in: 0,
  tokens_out: 0,
  cost_usd: 0,
  unpriced_spans: 0,
  retries: 0,
  fallbacks: 0,
  ...overrides,
})

export const makeTrace = (overrides: Partial<RunTrace> = {}): RunTrace => ({
  run_id: 'run-1',
  advisory_no: 3,
  spans: [],
  advisory_totals: makeTotals(),
  run_totals: makeTotals(),
  ...overrides,
})
