import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ExplainDrawer } from './ExplainDrawer'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

test('loads the explanation, and retries after an error', async () => {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(json({ error: { code: 'not_found', message: 'advisory 3 has not been issued' } }, 404))
    .mockResolvedValueOnce(json({ error: { code: 'internal', message: 'still failing' } }, 500))

  render(<ExplainDrawer assetId="SUB-07" advisoryNo={3} onClose={() => {}} />)

  expect(screen.getByText(/loading the explanation/i)).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('advisory 3 has not been issued')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/still failing/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/assets/SUB-07/explain?advisory=3', expect.anything())
})

test('close hands control back', async () => {
  vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))
  const onClose = vi.fn()
  render(<ExplainDrawer assetId="SUB-07" advisoryNo={3} onClose={onClose} />)

  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(onClose).toHaveBeenCalledOnce()
})
