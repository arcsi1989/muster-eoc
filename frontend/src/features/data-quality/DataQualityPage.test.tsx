import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { DataQualityPage } from './DataQualityPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

test('shows the loaded files once the lineage arrives', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    json([{ file: 'assets.json', sha256: 'a'.repeat(64), loaded_at: '2026-09-01T00:00:00Z', rows_ok: 196, rows_rejected: 0, issues: [] }]),
  )

  render(<DataQualityPage />)

  expect(screen.getByText(/loading the lineage/i)).toBeInTheDocument()
  expect(await screen.findByText('assets.json')).toBeInTheDocument()
})

test('an error offers a retry that loads again', async () => {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(json({ error: { code: 'internal', message: 'database locked' } }, 500))
    .mockResolvedValueOnce(json([]))

  render(<DataQualityPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/no files were loaded/i)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
