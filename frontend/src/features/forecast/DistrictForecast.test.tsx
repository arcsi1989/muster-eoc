import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import { makeDistrictForecast, makeForecast } from '../../test/fixtures'
import { ForecastPanel } from './DistrictForecast'

const FORECAST = makeForecast(3, [
  makeDistrictForecast({ district: 'Westshore', crews_needed: { p50: 3, p90: 49 }, crews_available: 4 }),
  makeDistrictForecast({
    district: 'Eastern Plains',
    power_customers: { p50: 0, p90: 0 },
    water_customers: { p50: 0, p90: 0 },
    crews_needed: { p50: 0, p90: 2 },
    generators_needed: { p50: 0, p90: 0 },
    crews_available: 4,
  }),
])

test('each district shows customers out, crews needed against available and generators, as P50–P90', () => {
  render(<ForecastPanel state={{ status: 'ok', data: FORECAST }} onRetry={() => {}} />)

  const table = screen.getByRole('table', { name: 'Outage forecast by district, advisory 3' })
  const rows = within(table).getAllByRole('row').slice(1)
  expect(rows.map((r) => within(r).getByRole('rowheader').textContent)).toEqual(['Westshore', 'Eastern Plains'])
  expect(within(rows[0]).getAllByRole('cell').map((c) => c.textContent)).toEqual([
    '26.7k–113.1k',
    '5.7k–114.8k',
    '3–49 / 4 short at P90',
    '10–17',
  ])
  // nothing at risk: one value, and no shortfall
  expect(within(rows[1]).getAllByRole('cell').map((c) => c.textContent)).toEqual(['0', '0', '0–2 / 4', '0'])
  expect(screen.getByText(/6 fuelled generators serve the whole territory/)).toBeInTheDocument()
  expect(screen.getByText(/not a decision/)).toBeInTheDocument()
})

test('before advisory 1 there is nothing to forecast', () => {
  render(<ForecastPanel state={{ status: 'idle' }} onRetry={() => {}} />)

  expect(screen.getByText('Issue advisory 1 to see the outage forecast.')).toBeInTheDocument()
})

test('while loading it says so, unless an earlier forecast is still shown', () => {
  const { rerender } = render(<ForecastPanel state={{ status: 'loading' }} onRetry={() => {}} />)
  expect(screen.getByText('Loading the outage forecast…')).toBeInTheDocument()

  rerender(<ForecastPanel state={{ status: 'loading' }} shown={FORECAST} onRetry={() => {}} />)
  expect(screen.getByRole('table')).toBeInTheDocument()
})

test('a failed load shows the error with a retry', async () => {
  const retry = vi.fn()
  render(
    <ForecastPanel
      state={{ status: 'error', error: new ApiError(503, 'unavailable', 'Forecast unavailable') }}
      onRetry={retry}
    />,
  )

  expect(screen.getByRole('alert')).toHaveTextContent('Could not load the outage forecast: Forecast unavailable')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(retry).toHaveBeenCalledOnce()
})

test('a forecast without districts says so', () => {
  render(<ForecastPanel state={{ status: 'ok', data: makeForecast(2, []) }} onRetry={() => {}} />)

  expect(screen.getByText('No forecast for advisory 2.')).toBeInTheDocument()
})
