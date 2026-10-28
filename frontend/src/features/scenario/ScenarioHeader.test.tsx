import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Scenario } from '../../types/scenario'
import { ScenarioHeader } from './ScenarioHeader'

const HOURS = [72, 60, 48, 36, 24]

const scenario = (current: number): Scenario => ({
  total_advisories: 5,
  current_advisory: current,
  timeline: HOURS.map((h, i) => ({
    advisory_no: i + 1,
    hours_to_landfall: h,
    activation_level: h > 48 ? 'prepare' : 'full',
    issued: i + 1 <= current,
  })),
  advisories: [],
})

const noop = () => {}

test('the timeline shows every advisory and marks the current one', () => {
  render(<ScenarioHeader scenario={scenario(3)} busy={false} actionError={null} onNext={noop} onReset={noop} />)

  for (const h of HOURS) expect(screen.getByText(`T-${h} h`)).toBeInTheDocument()
  const current = screen.getByRole('listitem', { current: 'step' })
  expect(current).toHaveTextContent('T-48 h')
  expect(screen.getByText('Advisory 5, not yet issued')).toBeInTheDocument()
})

test('the timeline shows when full activation starts', () => {
  render(<ScenarioHeader scenario={scenario(0)} busy={false} actionError={null} onNext={noop} onReset={noop} />)

  expect(screen.getByText('Prepare')).toBeInTheDocument()
  expect(screen.getByText('Full activation')).toBeInTheDocument()
})

test('the button names the advisory it issues', async () => {
  const onNext = vi.fn()
  render(<ScenarioHeader scenario={scenario(2)} busy={false} actionError={null} onNext={onNext} onReset={noop} />)

  await userEvent.click(screen.getByRole('button', { name: 'Issue advisory 3 ▶' }))
  expect(onNext).toHaveBeenCalledOnce()
})

test('after the last advisory the button is disabled', () => {
  render(<ScenarioHeader scenario={scenario(5)} busy={false} actionError={null} onNext={noop} onReset={noop} />)

  expect(screen.getByRole('button', { name: /last advisory/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Reset' })).toBeEnabled()
})
