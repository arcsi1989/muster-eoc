import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import { makeAsset } from '../../test/fixtures'
import type { Asset } from '../../types/scenario'
import { RiskPanel } from './RiskPanel'

const assetsById = new Map<string, Asset>([
  ['SUB-07', makeAsset({ id: 'SUB-07', name: 'Medical District Substation', type: 'substation' })],
  ['PS-14', makeAsset({ id: 'PS-14', name: 'Seawall Pumping Station', type: 'pump_station' })],
])

test('before advisory 1 it tells the operator to advance', () => {
  render(<RiskPanel state={{ status: 'idle' }} assetsById={assetsById} onRetry={() => {}} />)

  expect(screen.getByText(/issue advisory 1/i)).toBeInTheDocument()
})

test('shows a loading message while the list loads', () => {
  render(<RiskPanel state={{ status: 'loading' }} assetsById={assetsById} onRetry={() => {}} />)

  expect(screen.getByText(/loading the risk list/i)).toBeInTheDocument()
})

test('shows the error with a working retry', async () => {
  const onRetry = vi.fn()
  render(
    <RiskPanel
      state={{ status: 'error', error: new ApiError(502, 'upstream_error', 'backend unavailable') }}
      assetsById={assetsById}
      onRetry={onRetry}
    />,
  )

  expect(screen.getByRole('alert')).toHaveTextContent('backend unavailable')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(onRetry).toHaveBeenCalledOnce()
})

test('lists assets in rank order with their names and scores', () => {
  render(
    <RiskPanel
      state={{
        status: 'ok',
        data: {
          advisory_no: 1,
          items: [
            { asset_id: 'SUB-07', score: 0.81, rank: 1, previous_rank: 4 },
            { asset_id: 'PS-14', score: 0.4, rank: 2, previous_rank: 1 },
          ],
        },
      }}
      assetsById={assetsById}
      onRetry={() => {}}
    />,
  )

  const rows = screen.getAllByRole('listitem')
  expect(rows[0]).toHaveTextContent('SUB-07 Medical District Substation')
  expect(rows[0]).toHaveTextContent('0.81')
  expect(rows[1]).toHaveTextContent('PS-14 Seawall Pumping Station')
})

test('shows how each asset moved since the previous advisory', () => {
  render(
    <RiskPanel
      state={{
        status: 'ok',
        data: {
          advisory_no: 2,
          items: [
            { asset_id: 'SUB-07', score: 0.81, rank: 1, previous_rank: 4 },
            { asset_id: 'PS-14', score: 0.4, rank: 2, previous_rank: 1 },
          ],
        },
      }}
      assetsById={assetsById}
      onRetry={() => {}}
    />,
  )

  expect(screen.getByLabelText('up 3 from 4')).toHaveTextContent('▲3')
  expect(screen.getByLabelText('down 1 from 1')).toHaveTextContent('▼1')
})

test('says so when an advisory scored no assets', () => {
  render(<RiskPanel state={{ status: 'ok', data: { advisory_no: 1, items: [] } }} assetsById={assetsById} onRetry={() => {}} />)

  expect(screen.getByText(/no assets were scored/i)).toBeInTheDocument()
})
