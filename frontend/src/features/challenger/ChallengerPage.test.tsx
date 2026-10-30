import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type {
  Challenger,
  Disagreements,
  ModelMetrics,
  ModelVersion,
  ReliabilityBin,
  Scenario,
} from '../../types/scenario'
import { ChallengerPage } from './ChallengerPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const failure = (code: string, message: string, status: number) => json({ error: { code, message } }, status)

const bins = (rates: (number | null)[]): ReliabilityBin[] =>
  rates.map((rate, b) => ({
    lower: b / 10,
    upper: (b + 1) / 10,
    count: rate === null ? 0 : 5,
    mean_predicted: rate === null ? null : (b + 0.5) / 10,
    observed_rate: rate,
  }))

const metrics = (overrides: Partial<ModelMetrics>): ModelMetrics => ({
  assets: 196,
  failures: 51,
  brier: 0.172,
  roc_auc: 0.71,
  top_fraction: 0.1,
  top_capture: 0.275,
  reliability: bins([0.0, 0.1, null, 0.3, 0.4, 0.5, null, 0.7, 0.8, 0.9]),
  ...overrides,
})

const version = (overrides: Partial<ModelVersion>): ModelVersion => ({
  id: 3,
  label: 'challenger-hgb-20storms-seed42',
  kind: 'challenger',
  status: 'shadow',
  in_use: false,
  curves: [],
  created_at: '2026-10-30T09:00:00Z',
  approved_by: null,
  approved_at: null,
  ...overrides,
})

const challenger = (passed = true): Challenger => ({
  model_version: version({}),
  challenger: metrics({ brier: 0.15, roc_auc: 0.78, top_capture: 0.294 }),
  champion: metrics({}),
  promotion: {
    storm: 'Storm Delta',
    passed,
    criteria: [
      { name: 'brier_improvement', value: 0.022, threshold: 0.01, passed: true },
      { name: 'top_capture_gain', value: passed ? 0.019 : 0.004, threshold: 0.01, passed },
      { name: 'calibration_error', value: 0.12, threshold: 0.15, passed: true },
    ],
  },
})

const scenario = (current: number): Scenario => ({
  total_advisories: 5,
  current_advisory: current,
  timeline: [],
  advisories: [],
})

const disagreements = (items: Disagreements['items']): Disagreements => ({
  advisory_no: 2,
  model_version: 3,
  top_n: 10,
  items,
})

const ps31 = {
  asset_id: 'PS-31',
  asset_name: 'Old Harbour Pumping Station',
  challenger_rank: 4,
  champion_rank: 23,
  challenger_p_fail: 0.62,
  champion_p_fail: 0.31,
  top_features: [
    { feature: 'age_years', value: 55, contribution: 0.18 },
    { feature: 'condition_score', value: 5, contribution: 0.09 },
    { feature: 'wind_p90_mph', value: 96.4, contribution: 0.05 },
  ],
}

/** Answers by method and path, so the order of calls doesn't matter. */
function backend(routes: Record<string, () => Response>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const route = routes[key]
    if (!route) throw new Error(`unexpected request ${key}`)
    return route()
  })
}

const atAdvisory2 = (overrides: Record<string, () => Response> = {}) =>
  backend({
    'GET /api/challenger': () => json(challenger()),
    'GET /api/advisories': () => json(scenario(2)),
    'GET /api/challenger/disagreements?advisory=2': () => json(disagreements([ps31])),
    ...overrides,
  })

test('shows both reliability curves and both models’ metrics on the held-out storm', async () => {
  atAdvisory2()

  render(<ChallengerPage />)

  expect(screen.getByText(/loading the challenger/i)).toBeInTheDocument()
  const chart = await screen.findByRole('img', { name: /reliability/i })
  expect(within(chart).getByLabelText(/champion: published curves/i)).toBeInTheDocument()
  expect(within(chart).getByLabelText(/challenger: version 3/i)).toBeInTheDocument()
  expect(within(chart).getByLabelText(/perfect calibration/i)).toBeInTheDocument()

  expect(screen.getByRole('heading', { name: /held-out storm storm delta: 196 assets, 51 failed/i })).toBeInTheDocument()
  const table = screen.getByRole('table', { name: /metrics on the held-out storm/i })
  expect(within(table).getByRole('row', { name: /brier score/i })).toHaveTextContent(/0\.172.*0\.150/)
  expect(within(table).getByRole('row', { name: /roc auc/i })).toHaveTextContent(/0\.710.*0\.780/)
  expect(within(table).getByRole('row', { name: /top-10% capture/i })).toHaveTextContent(/28%.*29%/)
})

test('a failed load offers a retry that loads again', async () => {
  let calls = 0
  atAdvisory2({
    'GET /api/challenger': () =>
      ++calls === 1 ? failure('internal', 'database locked', 500) : json(challenger()),
  })

  render(<ChallengerPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByRole('table', { name: /metrics on the held-out storm/i })).toBeInTheDocument()
})

test('without a trained challenger it says how to get one', async () => {
  backend({ 'GET /api/challenger': () => failure('not_found', 'no challenger model is loaded', 404) })

  render(<ChallengerPage />)

  expect(await screen.findByText(/no challenger model is loaded: run make train/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /propose/i })).not.toBeInTheDocument()
})

test('lists the challenger’s top-10 assets the champion leaves out, and why', async () => {
  atAdvisory2()

  render(<ChallengerPage />)

  const list = await screen.findByRole('table', { name: /disagreements list/i })
  const row = within(list).getByRole('row', { name: /PS-31 Old Harbour Pumping Station/ })
  expect(row).toHaveTextContent(/rank 4 · 62%.*rank 23 · 31%/)
  const why = within(row).getByRole('list', { name: /why the challenger ranks PS-31/i })
  expect(within(why).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
    'Age 55 years +18 pts',
    'Condition score 5/5 +9 pts',
    'Wind P90 96 mph +5 pts',
  ])
  expect(screen.getByRole('heading', { name: /disagreements at advisory 2/i })).toBeInTheDocument()
})

test('with no disagreements it says so', async () => {
  atAdvisory2({ 'GET /api/challenger/disagreements?advisory=2': () => json(disagreements([])) })

  render(<ChallengerPage />)

  expect(await screen.findByText(/no disagreements: the challenger ranks no asset in its top 10/i)).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: /disagreements list/i })).not.toBeInTheDocument()
})

test('before any advisory there is nothing to compare yet', async () => {
  backend({ 'GET /api/challenger': () => json(challenger()), 'GET /api/advisories': () => json(scenario(0)) })

  render(<ChallengerPage />)

  expect(await screen.findByText(/no advisory issued yet/i)).toBeInTheDocument()
})

test('a failed disagreements load offers a retry', async () => {
  let calls = 0
  atAdvisory2({
    'GET /api/challenger/disagreements?advisory=2': () =>
      ++calls === 1 ? failure('internal', 'shadow scores unavailable', 500) : json(disagreements([ps31])),
  })

  render(<ChallengerPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('shadow scores unavailable')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByRole('table', { name: /disagreements list/i })).toBeInTheDocument()
})

test('a challenger failing the rule is never offered for promotion', async () => {
  atAdvisory2({ 'GET /api/challenger': () => json(challenger(false)) })

  render(<ChallengerPage />)

  const promotion = await screen.findByRole('region', { name: 'Promotion' })
  expect(within(promotion).getByRole('row', { name: /top-decile capture higher by/i })).toHaveTextContent(/failed/)
  expect(promotion).toHaveTextContent(/does not allow a proposal: top-decile capture higher by failed/i)
  expect(within(promotion).queryByRole('button')).not.toBeInTheDocument()
})

test('a passing challenger is proposed, then approved by the chosen role, and becomes champion', async () => {
  const fetchMock = atAdvisory2({
    'POST /api/challenger/propose': () => json(version({ status: 'proposed' })),
    'POST /api/model-versions/3/approve': () =>
      json(version({ status: 'approved', in_use: true, approved_by: 'director', approved_at: '2026-10-30T10:00:00Z' })),
  })

  render(<ChallengerPage />)

  const promotion = await screen.findByRole('region', { name: 'Promotion' })
  expect(within(promotion).queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
  await userEvent.click(within(promotion).getByRole('button', { name: /propose the challenger/i }))

  await within(promotion).findByRole('button', { name: /approve the promotion/i })
  expect(promotion).toHaveTextContent(/model version 3 is proposed/i)
  await userEvent.selectOptions(within(promotion).getByRole('combobox'), 'director')
  await userEvent.click(within(promotion).getByRole('button', { name: /approve the promotion/i }))

  expect(await within(promotion).findByText(/the challenger was promoted by/i)).toBeInTheDocument()
  expect(within(promotion).queryByRole('button')).not.toBeInTheDocument()
  const approval = fetchMock.mock.calls.find(([url]) => String(url) === '/api/model-versions/3/approve')
  expect(JSON.parse(String(approval?.[1]?.body))).toEqual({ role: 'director' })
})

test('a refused approval is shown and the promotion stays proposed', async () => {
  atAdvisory2({
    'GET /api/challenger': () => json({ ...challenger(), model_version: version({ status: 'proposed' }) }),
    'POST /api/model-versions/3/approve': () => failure('invalid_role', 'this role cannot approve a model', 422),
  })

  render(<ChallengerPage />)

  const promotion = await screen.findByRole('region', { name: 'Promotion' })
  await userEvent.click(within(promotion).getByRole('button', { name: /approve the promotion/i }))

  expect(await within(promotion).findByRole('alert')).toHaveTextContent('this role cannot approve a model')
  expect(within(promotion).getByRole('button', { name: /approve the promotion/i })).toBeEnabled()
})
