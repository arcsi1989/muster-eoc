import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { FieldTask } from '../../types/scenario'
import { FieldPage } from './FieldPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const DISTRICTS = ['Bayport East', 'Bayport West', 'Eastern Plains', 'Westshore']

const task = (overrides: Partial<FieldTask> = {}): FieldTask => ({
  item_id: 12,
  approved_in: 3,
  rule_id: 'P-4.2',
  why: 'Pre-inspect coastal pumping stations at flood risk',
  action: 'Inspect PS-14 Harbour Road pumping station before landfall',
  entity_id: 'PS-14',
  entity_name: 'Harbour Road pumping station',
  approved_by: 'incident_commander',
  approved_at: '2026-10-30T09:15:00Z',
  stop_work: [],
  status: 'open',
  note: null,
  reported_at: null,
  ...overrides,
})

/** Answers by URL; `tasks` may change between calls. */
function backend(tasks: () => FieldTask[] | Response, post?: () => Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url === '/api/field/districts') return json(DISTRICTS)
    if (url.startsWith('/api/field/tasks?')) {
      const t = tasks()
      return t instanceof Response ? t : json(t)
    }
    if (post) return post()
    throw new Error(`unexpected ${url}`)
  })
}

test('lists the first district’s tasks with what, where, why, clause and who approved them', async () => {
  const fetchMock = backend(() => [task()])

  render(<FieldPage />)

  expect(screen.getByText(/loading/i)).toBeInTheDocument()
  const card = await screen.findByRole('listitem')
  expect(fetchMock).toHaveBeenCalledWith('/api/field/tasks?district=Bayport%20East', expect.anything())
  expect(within(card).getByText('Inspect PS-14 Harbour Road pumping station before landfall')).toBeInTheDocument()
  expect(within(card).getByText('PS-14 Harbour Road pumping station')).toBeInTheDocument()
  expect(within(card).getByText('Pre-inspect coastal pumping stations at flood risk')).toBeInTheDocument()
  expect(within(card).getByText('P-4.2')).toBeInTheDocument()
  expect(within(card).getByText(/approved by Incident Commander at advisory 3, 30 Oct/i)).toBeInTheDocument()
  expect(within(card).getByRole('button', { name: 'Done' })).toBeEnabled()
})

test('choosing another district loads its tasks', async () => {
  const fetchMock = backend(() => [])
  render(<FieldPage />)
  await screen.findByText(/no approved field tasks/i)

  await userEvent.selectOptions(screen.getByLabelText(/district/i), 'Westshore')

  expect(fetchMock).toHaveBeenLastCalledWith('/api/field/tasks?district=Westshore', expect.anything())
})

test('a task under stop-work shows it and cannot be marked done', async () => {
  backend(() => [task({ stop_work: ['P-4.7'] })])

  render(<FieldPage />)

  const card = await screen.findByRole('listitem')
  expect(within(card).getByText('Stop work: P-4.7')).toBeInTheDocument()
  expect(within(card).getByRole('button', { name: 'Done' })).toBeDisabled()
  expect(within(card).getByRole('button', { name: /blocked/i })).toBeEnabled()
})

test('Done reports to the backend and the list shows the result', async () => {
  let tasks = [task()]
  const fetchMock = backend(
    () => tasks,
    () => {
      tasks = [task({ status: 'done', reported_at: '2026-10-30T10:00:00Z' })]
      return json(tasks)
    },
  )
  render(<FieldPage />)
  const card = await screen.findByRole('listitem')

  await userEvent.click(within(card).getByRole('button', { name: 'Done' }))

  expect(fetchMock).toHaveBeenCalledWith('/api/field/tasks/12/done', {
    method: 'POST',
    body: JSON.stringify({ district: 'Bayport East' }),
    headers: expect.anything(),
  })
  expect(await within(card).findByText('Done', { selector: '.badge' })).toBeInTheDocument()
  expect(within(card).queryByRole('button', { name: 'Done' })).not.toBeInTheDocument()
})

test('Blocked sends the note and the card shows it', async () => {
  let tasks = [task()]
  const fetchMock = backend(
    () => tasks,
    () => {
      tasks = [task({ status: 'blocked', note: 'Road flooded' })]
      return json(tasks)
    },
  )
  render(<FieldPage />)
  const card = await screen.findByRole('listitem')

  await userEvent.click(within(card).getByRole('button', { name: /blocked/i }))
  const send = within(card).getByRole('button', { name: 'Report blocked' })
  expect(send).toBeDisabled()
  await userEvent.type(within(card).getByLabelText(/what blocks it/i), '  Road flooded ')
  await userEvent.click(send)

  expect(fetchMock).toHaveBeenCalledWith('/api/field/tasks/12/blocked', {
    method: 'POST',
    body: JSON.stringify({ district: 'Bayport East', note: 'Road flooded' }),
    headers: expect.anything(),
  })
  expect(await within(card).findByText('Blocked', { selector: '.badge' })).toBeInTheDocument()
  expect(within(card).getByText(/“Road flooded”/)).toBeInTheDocument()
  // a blocked task may still be reported done
  expect(within(card).getByRole('button', { name: 'Done' })).toBeEnabled()
})

test('a refused report shows the reason on the card and reloads the list', async () => {
  let loads = 0
  backend(
    () => {
      loads += 1
      return [task({ stop_work: loads > 1 ? ['P-4.7'] : [] })]
    },
    () => json({ error: { code: 'stop_work', message: 'Stop work where tropical-storm-force wind arrives' } }, 409),
  )
  render(<FieldPage />)
  const card = await screen.findByRole('listitem')

  await userEvent.click(within(card).getByRole('button', { name: 'Done' }))

  expect(await within(card).findByRole('alert')).toHaveTextContent('tropical-storm-force wind')
  expect(await within(card).findByText('Stop work: P-4.7')).toBeInTheDocument()
})

test('an error loading the tasks offers a retry', async () => {
  let calls = 0
  backend(() => {
    calls += 1
    return calls === 1 ? json({ error: { code: 'internal', message: 'database locked' } }, 500) : []
  })

  render(<FieldPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/no approved field tasks/i)).toBeInTheDocument()
})
