import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import type { AdvisoryChanges, Asset } from '../../types/scenario'
import { ChangesPanel } from './ChangesPanel'

const assetsById = new Map<string, Asset>([
  ['SUB-07', { id: 'SUB-07', name: 'Medical District Substation', type: 'substation', x_km: 1, y_km: 2, customers_served: 10 }],
])

const changes = (overrides: Partial<AdvisoryChanges>): AdvisoryChanges => ({
  advisory_no: 3,
  previous_advisory_no: 2,
  landfall_shift: null,
  max_wind_change_mph: 0,
  peak_surge_change_m: 0,
  activation_level_from: 'prepare',
  activation_level_to: 'prepare',
  top10_entered: [],
  top10_left: [],
  rank_moves: [],
  ...overrides,
})

test('at the first advisory everything is initial', () => {
  render(
    <ChangesPanel
      state={{ status: 'ok', data: changes({ advisory_no: 1, previous_advisory_no: null }) }}
      assetsById={assetsById}
      onRetry={() => {}}
    />,
  )

  expect(screen.getByText(/initial forecast/i)).toBeInTheDocument()
})

test('describes the landfall shift, the new activation level and the biggest rank move', () => {
  render(
    <ChangesPanel
      state={{
        status: 'ok',
        data: changes({
          landfall_shift: { distance_km: 41.3, direction: 'east' },
          activation_level_to: 'full',
          rank_moves: [{ asset_id: 'SUB-07', from_rank: 4, to_rank: 1 }],
        }),
      }}
      assetsById={assetsById}
      onRetry={() => {}}
    />,
  )

  expect(screen.getByText('Forecast landfall moved 41 km east.')).toBeInTheDocument()
  expect(screen.getByText('Activation level is now Full activation.')).toBeInTheDocument()
  expect(screen.getByText('SUB-07 Medical District Substation rose from rank 4 to 1.')).toBeInTheDocument()
})

test('says so when nothing changed', () => {
  render(<ChangesPanel state={{ status: 'ok', data: changes({}) }} assetsById={assetsById} onRetry={() => {}} />)

  expect(screen.getByText(/no change/i)).toBeInTheDocument()
})

test('shows an error with a working retry', async () => {
  const onRetry = vi.fn()
  render(
    <ChangesPanel
      state={{ status: 'error', error: new ApiError(500, 'internal', 'boom') }}
      assetsById={assetsById}
      onRetry={onRetry}
    />,
  )

  expect(screen.getByRole('alert')).toHaveTextContent('boom')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(onRetry).toHaveBeenCalledOnce()
})
