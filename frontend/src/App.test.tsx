import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'

// Every page loads its own data; here every request fails, so pages show their error states and
// the test sees only the frame around them: the nav, the copilot dock and the side panel tabs.
beforeEach(() => {
  window.location.hash = '#/'
  vi.spyOn(globalThis, 'fetch').mockImplementation(
    async () => new Response(JSON.stringify({ error: { code: 'internal', message: 'offline' } }), { status: 500 }),
  )
})
afterEach(() => vi.restoreAllMocks())

async function go(hash: string) {
  await act(async () => {
    window.location.hash = hash
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
}

test('the copilot opens from the header on every page and stays open across page changes', async () => {
  render(<App />)
  const button = screen.getByRole('button', { name: 'Copilot' })
  expect(screen.queryByRole('complementary', { name: 'Copilot' })).not.toBeInTheDocument()

  await userEvent.click(button)

  expect(button).toHaveAttribute('aria-expanded', 'true')
  const dock = screen.getByRole('complementary', { name: 'Copilot' })
  await userEvent.type(within(dock).getByLabelText('Ask the copilot'), 'half-typed question')
  for (const hash of ['#/operations', '#/audit', '#/trace', '#/']) {
    await go(hash)
    expect(screen.getByRole('complementary', { name: 'Copilot' })).toBeVisible()
  }
  expect(within(dock).getByLabelText('Ask the copilot')).toHaveValue('half-typed question')

  await userEvent.click(within(dock).getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('complementary', { name: 'Copilot' })).not.toBeInTheDocument()
})

test('the operations side panel has no copilot tab', async () => {
  await go('#/operations')
  render(<App />)

  const tabs = within(screen.getByRole('tablist', { name: 'Side panel' })).getAllByRole('tab')
  expect(tabs.map((t) => t.textContent)).toEqual(['Risk list', 'Decision package'])
})
