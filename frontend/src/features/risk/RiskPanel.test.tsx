import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import { makeAsset, makeRiskItem } from '../../test/fixtures'
import type { Asset } from '../../types/scenario'
import { RiskPanel } from './RiskPanel'

const assetsById = new Map<string, Asset>([
  ['SUB-07', makeAsset({ id: 'SUB-07', name: 'Medical District Substation', type: 'substation' })],
  ['PS-14', makeAsset({ id: 'PS-14', name: 'Seawall Pumping Station', type: 'pump_station' })],
])

const noop = () => {}

test('before advisory 1 it tells the operator to issue one', () => {
  render(<RiskPanel state={{ status: 'idle' }} assetsById={assetsById} onRetry={noop} onSelect={noop} />)

  expect(screen.getByText(/issue advisory 1/i)).toBeInTheDocument()
})

test('shows a loading message while the list loads', () => {
  render(<RiskPanel state={{ status: 'loading' }} assetsById={assetsById} onRetry={noop} onSelect={noop} />)

  expect(screen.getByText(/loading the risk list/i)).toBeInTheDocument()
})

test('shows the error with a working retry', async () => {
  const onRetry = vi.fn()
  render(
    <RiskPanel
      state={{ status: 'error', error: new ApiError(502, 'upstream_error', 'backend unavailable') }}
      assetsById={assetsById}
      onRetry={onRetry}
      onSelect={noop}
    />,
  )

  expect(screen.getByRole('alert')).toHaveTextContent('backend unavailable')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(onRetry).toHaveBeenCalledOnce()
})

const twoItems = {
  status: 'ok' as const,
  data: {
    advisory_no: 2,
    model_version: 1,
    items: [
      makeRiskItem({ asset_id: 'SUB-07', rank: 1, previous_rank: 4, risk: 12300, confidence: 'medium' }),
      makeRiskItem({ asset_id: 'PS-14', rank: 2, previous_rank: 1, risk: 800 }),
    ],
  },
}

test('lists assets in rank order with name, risk and a confidence warning', () => {
  render(<RiskPanel state={twoItems} assetsById={assetsById} onRetry={noop} onSelect={noop} />)

  const rows = screen.getAllByRole('listitem')
  expect(rows[0]).toHaveTextContent('SUB-07 Medical District Substation')
  expect(rows[0]).toHaveTextContent('12.3k')
  expect(rows[0]).toHaveTextContent('medium confidence')
  expect(rows[1]).toHaveTextContent('PS-14 Seawall Pumping Station')
  expect(rows[1]).not.toHaveTextContent('confidence')
})

test('shows how each asset moved since the previous advisory', () => {
  render(<RiskPanel state={twoItems} assetsById={assetsById} onRetry={noop} onSelect={noop} />)

  expect(screen.getByLabelText('up 3 from 4')).toHaveTextContent('▲3')
  expect(screen.getByLabelText('down 1 from 1')).toHaveTextContent('▼1')
})

test('clicking a row asks for its explanation', async () => {
  const onSelect = vi.fn()
  render(<RiskPanel state={twoItems} assetsById={assetsById} onRetry={noop} onSelect={onSelect} />)

  await userEvent.click(screen.getByRole('button', { name: /PS-14/ }))
  expect(onSelect).toHaveBeenCalledWith('PS-14')
})

test('says so when an advisory scored no assets', () => {
  render(
    <RiskPanel state={{ status: 'ok', data: { advisory_no: 1, model_version: 1, items: [] } }} assetsById={assetsById} onRetry={noop} onSelect={noop} />,
  )

  expect(screen.getByText(/no assets were scored/i)).toBeInTheDocument()
})
