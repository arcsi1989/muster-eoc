import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { makeAsset } from '../../test/fixtures'
import type { Explanation } from '../../types/scenario'
import { ExplainPanel } from './ExplainPanel'

const explanation: Explanation = {
  asset: makeAsset({ id: 'SUB-07', name: 'Medical District Substation', type: 'substation', condition_score: 4 }),
  advisory_no: 3,
  rank: 16,
  risk: 3200,
  p_fail: 0.28,
  p_wind: 0.27,
  p_flood: 0.02,
  wind: { theta: 140, theta_adjusted: 105, beta: 0.25, p_fail: 0.27 },
  flood: { theta: 0.8, theta_adjusted: 0.62, beta: 0.5, p_fail: 0.02 },
  exposure: {
    site_id: 'SUB-07',
    site_kind: 'asset',
    wind_p50_mph: 80.7,
    wind_p90_mph: 128.2,
    flood_depth_p50_m: 0,
    flood_depth_p90_m: 0.1,
    tsforce_arrival_h: 30,
    elevation_imputed: false,
  },
  consequence: {
    own_customers: 6000,
    downstream_assets: [{ id: 'PS-03', customers: 1500, feeders: 1 }],
    facilities: [{ id: 'HOSP-01', type: 'hospital', weight: 5000, feeders: 1 }],
    total: 12500,
  },
  confidence: 'medium',
  confidence_reasons: ['last inspection over 3 years ago (2022-05-01)'],
  feeds: [{ id: 'HOSP-01', kind: 'facility', name: 'Bayport General Hospital' }],
  fed_by: [],
  challenger: null,
}

test('explains rank, failure probability, condition and consequence', () => {
  render(<ExplainPanel explanation={explanation} />)

  expect(screen.getByText(/Rank 16/)).toBeInTheDocument()
  expect(screen.getByText('medium confidence')).toBeInTheDocument()
  expect(screen.getByText(/last inspection over 3 years/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Failure probability 28%' })).toBeInTheDocument()
  expect(screen.getByText(/Condition 4\/5 lowers its capacity by 25%/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Consequence 12.5k/ })).toBeInTheDocument()
  expect(screen.getByText(/HOSP-01 Bayport General Hospital/)).toBeInTheDocument()
  expect(screen.getByText(/no upstream asset/)).toBeInTheDocument()
})

test('shows the challenger in shadow beside the rule-based breakdown', () => {
  render(
    <ExplainPanel
      explanation={{
        ...explanation,
        challenger: {
          model_version: 3,
          rank: 4,
          p_fail: 0.61,
          top_features: [
            { feature: 'age_years', value: 52, contribution: 0.21 },
            { feature: 'condition_score', value: 5, contribution: 0.12 },
            { feature: 'asset_type', value: 'substation', contribution: -0.004 },
          ],
        },
      }}
    />,
  )

  expect(screen.getByRole('heading', { name: 'Failure probability 28%' })).toBeInTheDocument()
  const challenger = screen.getByRole('region', { name: /challenger in shadow/i })
  expect(within(challenger).getByRole('heading', { name: /challenger: rank 4 · 61%/i })).toBeInTheDocument()
  const features = within(challenger).getAllByRole('listitem')
  expect(features.map((f) => f.textContent)).toEqual([
    'Age 52 years +21 pts',
    'Condition score 5/5 +12 pts',
    'Asset type substation ±0 pts',
  ])
})

test('without a challenger score it shows the rule-based breakdown only', () => {
  render(<ExplainPanel explanation={explanation} />)
  expect(screen.queryByRole('region', { name: /challenger/i })).not.toBeInTheDocument()
})
