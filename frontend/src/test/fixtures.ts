import type { Asset, RiskItem } from '../types/scenario'

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
