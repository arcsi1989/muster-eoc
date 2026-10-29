import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import { AlertsPanel } from './AlertsPanel'

const noop = () => {}

test('lists alerts and opens the asset on click', async () => {
  const onSelect = vi.fn()
  render(
    <AlertsPanel
      state={{
        status: 'ok',
        data: [{ asset_id: 'SUB-11', kind: 'top_n_entry', message: 'Entered the top 10 (rank 14 → 5)' }],
      }}
      onRetry={noop}
      onSelect={onSelect}
    />,
  )

  expect(screen.getByText('Entered top')).toBeInTheDocument()
  expect(screen.getByText(/Entered the top 10/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'SUB-11' }))
  expect(onSelect).toHaveBeenCalledWith('SUB-11')
})

test('says so when there are no alerts', () => {
  render(<AlertsPanel state={{ status: 'ok', data: [] }} onRetry={noop} onSelect={noop} />)

  expect(screen.getByText(/no alerts/i)).toBeInTheDocument()
})

test('shows loading, and an error with a working retry', async () => {
  const { rerender } = render(<AlertsPanel state={{ status: 'loading' }} onRetry={noop} onSelect={noop} />)
  expect(screen.getByText(/loading alerts/i)).toBeInTheDocument()

  const onRetry = vi.fn()
  rerender(
    <AlertsPanel
      state={{ status: 'error', error: new ApiError(500, 'internal', 'database locked') }}
      onRetry={onRetry}
      onSelect={noop}
    />,
  )
  expect(screen.getByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(onRetry).toHaveBeenCalledOnce()
})
