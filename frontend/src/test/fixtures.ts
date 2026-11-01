import type { Asset, DistrictForecast, OutageForecast, RiskItem, RunTrace, TraceSpan, TraceTotals } from '../types/scenario'

export const makeAsset = (overrides: Partial<Asset> & Pick<Asset, 'id' | 'name' | 'type'>): Asset => ({
  x_km: 0,
  y_km: 0,
  elevation_m: 2,
  distance_to_coast_km: 5,
  install_year: 1990,
  condition_score: 3,
  last_inspection_date: '2026-01-01',
  customers_served: 1000,
  ...overrides,
})

export const makeRiskItem = (overrides: Partial<RiskItem> & Pick<RiskItem, 'asset_id' | 'rank'>): RiskItem => ({
  p_fail: 0.3,
  consequence: 10000,
  risk: 3000,
  previous_rank: null,
  confidence: 'high',
  risk_band: 'high',
  top_factor: 'wind',
  ...overrides,
})

export const makeDistrictForecast = (
  overrides: Partial<DistrictForecast> & Pick<DistrictForecast, 'district'>,
): DistrictForecast => ({
  power_customers: { p50: 26_700, p90: 113_100 },
  water_customers: { p50: 5_700, p90: 114_800 },
  failed_assets: { p50: 6, p90: 27 },
  crews_needed: { p50: 14, p90: 47 },
  generators_needed: { p50: 10, p90: 17 },
  crews_for_actions: 4,
  generators_for_actions: 9,
  crews_available: 8,
  crews_short_p90: 39,
  ...overrides,
})

export const makeForecast = (advisoryNo: number, districts: DistrictForecast[]): OutageForecast => ({
  advisory_no: advisoryNo,
  model_version: 1,
  samples: 1000,
  generators_available: 6,
  districts,
})

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
