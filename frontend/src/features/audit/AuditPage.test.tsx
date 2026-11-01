import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { AuditEvent } from '../../types/scenario'
import { AuditPage } from './AuditPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const event = (overrides: Partial<AuditEvent>): AuditEvent => ({
  id: 1,
  recorded_at: '2026-10-29T10:00:00Z',
  advisory_no: 3,
  hours_to_landfall: 48,
  actor: 'human',
  type: 'decision',
  summary: 'Incident commander overridden P-4.2 for PS-14: crew shortage, re-plan at next advisory',
  payload: { rule_id: 'P-4.2', role: 'incident_commander', action: 'override', reason: 'crew shortage' },
  input_hash: 'abc123',
  versions: { rules_version: '3.2', prompt_version: null },
  ...overrides,
})

test('lists events with scenario time, actor and expandable details', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    json([event({}), event({ id: 2, actor: 'system', type: 'items_not_decided', summary: '12 items closed as not decided', advisory_no: null, input_hash: 'def456', versions: {} })]),
  )

  render(<AuditPage />)

  expect(await screen.findByText(/crew shortage, re-plan at next advisory/)).toBeInTheDocument()
  expect(screen.getByText('Advisory 3 · T-48 h')).toBeInTheDocument()
  expect(screen.getByText('12 items closed as not decided')).toBeInTheDocument()
  expect(screen.getByText('Before advisory 1')).toBeInTheDocument()
  await userEvent.click(screen.getAllByText('Details')[0])
  expect(screen.getByText('abc123')).toBeInTheDocument()
  expect(screen.getByText('rules_version: 3.2')).toBeInTheDocument()
})

test('filtering by actor asks the backend for that actor', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => json([]))
  render(<AuditPage />)
  await screen.findByText(/no events yet/i)

  await userEvent.selectOptions(screen.getByLabelText(/show/i), 'human')

  expect(fetchMock).toHaveBeenLastCalledWith('/api/audit?actor=human', expect.anything())
})

test('an error offers a retry', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(json({ error: { code: 'internal', message: 'database locked' } }, 500))
    .mockResolvedValueOnce(json([]))

  render(<AuditPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/no events yet/i)).toBeInTheDocument()
})

test('shows a loading message, then who decided and which model ran', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    json([
      event({}),
      event({
        id: 3,
        actor: 'agent',
        type: 'sitrep_drafted',
        summary: 'Draft situation report written by anthropic',
        input_hash: 'ghi789',
        versions: {},
        payload: { attempts: [{ provider: 'anthropic', model: 'claude-sonnet-5-5', latency_ms: 2100, usage: { input_tokens: 3000, output_tokens: 600 } }] },
      }),
    ]),
  )

  render(<AuditPage />)

  expect(screen.getByText(/loading the audit log/i)).toBeInTheDocument()
  expect(await screen.findByText(/Role: Incident Commander · action: override · reason: “crew shortage”/)).toBeInTheDocument()
  expect(screen.getByText(/Model call 1: claude-sonnet-5-5 · 2100 ms · 3000 in \/ 600 out tokens/)).toBeInTheDocument()
})
