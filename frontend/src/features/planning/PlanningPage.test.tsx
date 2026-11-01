import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { makeDistrictForecast, makeForecast } from '../../test/fixtures'
import { packageResponse } from '../../test/packageResponse'
import type { DecisionPackage, Ics215Row, Planning, Scenario } from '../../types/scenario'
import { PlanningPage } from './PlanningPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const scenario = (current: number): Scenario => ({
  total_advisories: 5,
  current_advisory: current,
  timeline: [],
  advisories: [],
})

const pkg = (overrides: Partial<DecisionPackage> = {}): DecisionPackage => ({
  ...packageResponse,
  advisory_no: 4,
  decides_as_commander: 'incident_commander',
  ...overrides,
})

const row = (overrides: Partial<Ics215Row>): Ics215Row => ({
  item_id: 1,
  clause_id: 'P-4.5',
  location_id: 'PS-09',
  location: 'Harbour Road pumping station',
  work_assignment: 'Stage a portable generator at PS-09',
  resource_kind: 'portable generator',
  required: 1,
  have: 1,
  need: 0,
  reporting_location_id: 'STG-02',
  reporting_location: 'Bayport East depot',
  requested_arrival_hours: 36,
  stop_work: [],
  ...overrides,
})

const draft = (overrides: Partial<Planning> = {}): Planning => ({
  period_start_hours: 36,
  period_end_hours: 24,
  ics215: [
    row({}),
    row({
      item_id: 2,
      clause_id: 'P-4.2',
      location_id: 'SUB-11',
      location: 'Marsh Lane substation',
      work_assignment: 'Install a flood barrier at SUB-11',
      resource_kind: 'barrier crew',
      required: 2,
      have: 1,
      need: 1,
    }),
  ],
  objectives: [
    { text: 'Keep crews safe: no field work in tropical-storm wind.', clause_ids: ['P-4.7', 'P-8.2'], entity_ids: [] },
    {
      text: 'Protect water supply to WTP-01: generators at at-risk pumping stations by T-36.',
      clause_ids: ['P-4.5'],
      entity_ids: ['PS-09'],
    },
    { text: 'Keep the EOC coordinated.', clause_ids: ['P-4.1', 'P-7.1'], entity_ids: [] },
  ],
  provider: 'template',
  fallback: false,
  model: null,
  prompt_version: null,
  fallback_reason: null,
  advisory_no: 4,
  status: 'DRAFT',
  drafted_at: '2026-10-30T09:00:00Z',
  planning_approved_at: null,
  released_by: null,
  released_at: null,
  ...overrides,
})

const FORECAST = makeForecast(4, [
  makeDistrictForecast({ district: 'Bayport East', crews_needed: { p50: 16, p90: 36 }, crews_available: 0 }),
])

/** Answers by method and path, so the order of calls doesn't matter; records what was posted.
 * The forecast beside the worksheet is answered unless a test routes it. */
function backend(routes: Record<string, (body: unknown) => Response>) {
  const posted: { key: string; body: unknown }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const route = routes[key] ?? (key.startsWith('GET /api/forecast?') ? () => json(FORECAST) : undefined)
    if (!route) throw new Error(`unexpected request ${key}`)
    const body: unknown = init?.body ? JSON.parse(String(init.body)) : null
    if (init?.method === 'POST') posted.push({ key, body })
    return route(body)
  })
  return posted
}

const PLANNING = '/api/packages/4/planning'

test('the draft shows the ICS-215 rows and the objectives with their clause IDs, marked DRAFT', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft()),
  })

  render(<PlanningPage />)

  expect(await screen.findByText('DRAFT')).toBeInTheDocument()
  expect(screen.getByText(/operational period T-36 to T-24/)).toBeInTheDocument()

  const rows = within(screen.getByRole('table', { name: /ics-215/i })).getAllByRole('row')
  expect(rows).toHaveLength(3)
  const barrier = within(rows[2]).getAllByRole('cell').map((c) => c.textContent)
  expect(barrier).toEqual([
    'Marsh Lane substation (SUB-11)',
    'Install a flood barrier at SUB-11',
    'barrier crew',
    '2',
    '1',
    '1',
    'Bayport East depot (STG-02)',
    'T-36',
    'P-4.2',
  ])

  const objectives = within(screen.getByRole('region', { name: /iap objectives/i })).getAllByRole('listitem')
  expect(objectives).toHaveLength(3)
  expect(within(objectives[1]).getByText('P-4.5')).toBeInTheDocument()
  expect(within(objectives[0]).getByText('P-4.7')).toBeInTheDocument()
  expect(within(objectives[0]).getByText('P-8.2')).toBeInTheDocument()
  expect(screen.getByText(/template wording \(offline\)/i)).toBeInTheDocument()
})

test('a task under stop-work says so on its row', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft({ ics215: [row({ stop_work: ['P-4.7'] })] })),
  })

  render(<PlanningPage />)

  expect(await screen.findByText('Stop work: P-4.7')).toBeInTheDocument()
})

test('release takes the Planning Section Chief first, then the Incident Commander, and shows who and when', async () => {
  const user = userEvent.setup()
  const posted = backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft()),
    [`POST ${PLANNING}/release`]: (body) =>
      (body as { role: string }).role === 'planning'
        ? json(draft({ planning_approved_at: '2026-10-30T09:10:00Z' }))
        : json(
            draft({
              planning_approved_at: '2026-10-30T09:10:00Z',
              status: 'released',
              released_by: 'incident_commander',
              released_at: '2026-10-30T09:20:00Z',
            }),
          ),
  })

  render(<PlanningPage />)

  const release = await screen.findByRole('button', { name: /release as incident commander/i })
  expect(release).toBeDisabled()
  expect(screen.getByText(/after the planning section chief approves/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /approve as planning section chief/i }))

  expect(await screen.findByText(/approved by the planning section chief, 30 oct, 09:10 utc/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /approve as planning section chief/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /redraft/i })).not.toBeInTheDocument()
  expect(screen.getByText('DRAFT')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /release as incident commander/i }))

  expect(await screen.findByText(/released by the incident commander, 30 oct, 09:20 utc/i)).toBeInTheDocument()
  expect(screen.getByText('Released')).toBeInTheDocument()
  expect(screen.queryByText('DRAFT')).not.toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(posted.map((p) => p.body)).toEqual([{ role: 'planning' }, { role: 'incident_commander' }])
})

test('below Full activation the Director releases', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg({ decides_as_commander: 'director' })),
    [`GET ${PLANNING}`]: () => json(draft({ planning_approved_at: '2026-10-30T09:10:00Z' })),
  })

  render(<PlanningPage />)

  expect(await screen.findByRole('button', { name: /release as director/i })).toBeEnabled()
})

test('a released draft loads with who approved when and no controls', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () =>
      json(
        draft({
          status: 'released',
          planning_approved_at: '2026-10-30T09:10:00Z',
          released_by: 'incident_commander',
          released_at: '2026-10-30T09:20:00Z',
        }),
      ),
  })

  render(<PlanningPage />)

  expect(await screen.findByText('Released')).toBeInTheDocument()
  expect(screen.getByText(/approved by the planning section chief, 30 oct, 09:10 utc/i)).toBeInTheDocument()
  expect(screen.getByText(/released by the incident commander, 30 oct, 09:20 utc/i)).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('a refused approval shows why', async () => {
  const user = userEvent.setup()
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft()),
    [`POST ${PLANNING}/release`]: () =>
      json({ error: { code: 'decision_refused', message: 'The Planning Section Chief approves first.' } }, 403),
  })

  render(<PlanningPage />)
  await user.click(await screen.findByRole('button', { name: /approve as planning section chief/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/not done: the planning section chief approves first/i)
  expect(screen.getByText('DRAFT')).toBeInTheDocument()
})

test('with no draft yet the Planning Section Chief drafts one', async () => {
  const user = userEvent.setup()
  const posted = backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json({ error: { code: 'not_found', message: 'no planning draft for advisory 4' } }, 404),
    [`POST ${PLANNING}/draft`]: () => json(draft()),
  })

  render(<PlanningPage />)

  expect(await screen.findByText(/no planning draft for advisory 4 yet/i)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /draft the ics-215 and iap objectives/i }))

  expect(await screen.findByText('DRAFT')).toBeInTheDocument()
  expect(screen.getByRole('table', { name: /ics-215/i })).toBeInTheDocument()
  expect(posted.map((p) => p.key)).toEqual([`POST ${PLANNING}/draft`])
})

test('a draft with no approved field work says so', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft({ ics215: [] })),
  })

  render(<PlanningPage />)

  expect(await screen.findByText(/no approved field work for this period/i)).toBeInTheDocument()
})

test('a closed package offers no drafting or release', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg({ status: 'closed' })),
    [`GET ${PLANNING}`]: () => json(draft()),
  })

  render(<PlanningPage />)

  expect(await screen.findByText(/this draft was not released/i)).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('a failed load offers a retry that loads again', async () => {
  const user = userEvent.setup()
  let calls = 0
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () =>
      ++calls === 1 ? json({ error: { code: 'internal', message: 'database locked' } }, 500) : json(draft()),
  })

  render(<PlanningPage />)

  expect(screen.getByText(/loading the scenario/i)).toBeInTheDocument()
  expect(await screen.findByText(/could not load the planning draft: database locked/i)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /retry/i }))

  expect(await screen.findByText('DRAFT')).toBeInTheDocument()
})

test('before advisory 1 there is nothing to draft', async () => {
  backend({ 'GET /api/advisories': () => json(scenario(0)) })

  render(<PlanningPage />)

  expect(await screen.findByText(/no advisory issued yet/i)).toBeInTheDocument()
})

test('a template fallback says the AI wording was not used, with its reason when there is one', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft({ provider: 'template (fallback)', fallback: true, fallback_reason: null })),
  })

  render(<PlanningPage />)

  expect(await screen.findByText('Template wording (the AI wording was not used)')).toBeInTheDocument()
})

test('the forecast demand is shown beside the worksheet as context, never as worksheet rows', async () => {
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft()),
  })

  render(<PlanningPage />)

  const context = await screen.findByRole('complementary', { name: 'Forecast demand (context)' })
  const forecast = await within(context).findByRole('table', { name: 'Outage forecast by district, advisory 4' })
  expect(within(forecast).getByRole('row', { name: /^Bayport East/ })).toHaveTextContent('16–36 / 0 short')
  expect(context).toHaveTextContent('Not part of the ICS-215')
  expect(context).toHaveClass('no-print')
  // the worksheet keeps its two approved rows
  const rows = within(screen.getByRole('table', { name: /ics-215/i })).getAllByRole('row')
  expect(rows).toHaveLength(3)
  expect(within(screen.getByRole('table', { name: /ics-215/i })).queryByText('Bayport East')).not.toBeInTheDocument()
})

test('a failed forecast offers a retry and leaves the worksheet alone', async () => {
  let fail = true
  backend({
    'GET /api/advisories': () => json(scenario(4)),
    'GET /api/packages/4': () => json(pkg()),
    [`GET ${PLANNING}`]: () => json(draft()),
    'GET /api/forecast?advisory=4': () =>
      fail ? json({ error: { code: 'unavailable', message: 'Forecast unavailable' }}, 503) : json(FORECAST),
  })

  render(<PlanningPage />)

  const context = await screen.findByRole('complementary', { name: 'Forecast demand (context)' })
  expect(await within(context).findByRole('alert')).toHaveTextContent('Forecast unavailable')
  expect(screen.getByRole('table', { name: /ics-215/i })).toBeInTheDocument()
  fail = false
  await userEvent.click(within(context).getByRole('button', { name: 'Retry' }))
  expect(await within(context).findByRole('table')).toBeInTheDocument()
})
