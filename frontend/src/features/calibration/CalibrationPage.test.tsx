import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { Backtest, Calibration, ModelVersion, ReliabilityBin } from '../../types/scenario'
import { CalibrationPage } from './CalibrationPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const version = (overrides: Partial<ModelVersion>): ModelVersion => ({
  id: 1,
  label: 'Published curves',
  status: 'approved',
  in_use: true,
  curves: [],
  created_at: '2026-10-29T09:00:00Z',
  approved_by: null,
  approved_at: null,
  ...overrides,
})

const bins = (rates: (number | null)[]): ReliabilityBin[] =>
  rates.map((rate, b) => ({
    lower: b / 10,
    upper: (b + 1) / 10,
    count: rate === null ? 0 : 5,
    mean_predicted: rate === null ? null : (b + 0.5) / 10,
    observed_rate: rate,
  }))

const backtest = (overrides: Partial<Backtest>): Backtest => ({
  model_version: 1,
  assets: 196,
  failures: 51,
  brier: 0.2,
  top_fraction: 0.1,
  top_capture: 0.3,
  reliability: bins([0.0, 0.05, null, 0.2, 0.3, 0.4, null, 0.6, 0.7, 0.9]),
  ...overrides,
})

const proposed = version({ id: 2, label: 'Calibrated on Storm Delta', status: 'proposed', in_use: false })

const calibration: Calibration = {
  storm: 'Storm Delta',
  before: backtest({ brier: 0.184, top_capture: 0.294 }),
  after: backtest({ model_version: 2, brier: 0.152, top_capture: 0.333 }),
  model_version: proposed,
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

test('before a run it names the version in use and offers the back-test', async () => {
  backend({ 'GET /api/model-versions': () => json([version({})]) })

  render(<CalibrationPage />)

  expect(screen.getByText(/loading the model versions/i)).toBeInTheDocument()
  expect(await screen.findByText(/scoring uses version 1 \(published curves\)/i)).toBeInTheDocument()
  expect(screen.getByText(/no back-test run yet/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /run the back-test/i })).toBeEnabled()
})

test('a failed model-version load offers a retry that loads again', async () => {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(json({ error: { code: 'internal', message: 'database locked' } }, 500))
    .mockResolvedValueOnce(json([version({})]))

  render(<CalibrationPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/scoring uses version 1 \(published curves\)/i)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

test('a run shows both reliability curves and the scores before and after', async () => {
  backend({
    'GET /api/model-versions': () => json([version({})]),
    'POST /api/calibration/run': () => json(calibration),
  })

  render(<CalibrationPage />)
  await userEvent.click(await screen.findByRole('button', { name: /run the back-test/i }))

  const chart = await screen.findByRole('img', { name: /reliability/i })
  expect(within(chart).getByLabelText(/perfect calibration/i)).toBeInTheDocument()
  expect(within(chart).getByLabelText(/before: version 1/i)).toBeInTheDocument()
  expect(within(chart).getByLabelText(/after: version 2/i)).toBeInTheDocument()

  const scores = screen.getByRole('table', { name: /scores/i })
  expect(within(scores).getByRole('row', { name: /brier score/i })).toHaveTextContent(/0\.184.*0\.152/)
  expect(within(scores).getByRole('row', { name: /top-10% capture/i })).toHaveTextContent(/29%.*33%/)
})

test('a failed run offers a retry that runs again', async () => {
  let runs = 0
  backend({
    'GET /api/model-versions': () => json([version({})]),
    'POST /api/calibration/run': () =>
      ++runs === 1 ? json({ error: { code: 'data_not_loaded', message: 'Storm Delta missing' } }, 503) : json(calibration),
  })

  render(<CalibrationPage />)
  await userEvent.click(await screen.findByRole('button', { name: /run the back-test/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Storm Delta missing')
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByRole('table', { name: /scores/i })).toBeInTheDocument()
  expect(runs).toBe(2)
})

test('approving sends the chosen role and shows the version as approved and in use', async () => {
  const approved = { ...proposed, status: 'approved', in_use: true, approved_by: 'director', approved_at: '2026-10-29T10:00:00Z' }
  let afterApproval = false
  const fetchMock = backend({
    'GET /api/model-versions': () => json(afterApproval ? [version({ in_use: false }), approved] : [version({})]),
    'POST /api/calibration/run': () => json(calibration),
    'POST /api/model-versions/2/approve': () => {
      afterApproval = true
      return json(approved)
    },
  })

  render(<CalibrationPage />)
  await userEvent.click(await screen.findByRole('button', { name: /run the back-test/i }))
  await userEvent.selectOptions(await screen.findByLabelText(/deciding as/i), 'director')
  await userEvent.click(screen.getByRole('button', { name: /approve model version 2/i }))

  expect(await screen.findByText(/approved by director\. model version 2 \(calibrated on storm delta\) scores the next advisory/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /approve model version 2/i })).not.toBeInTheDocument()
  expect(await screen.findByText(/scoring uses version 2 \(calibrated on storm delta\), approved by director\./i)).toBeInTheDocument()
  const approveCall = fetchMock.mock.calls.find(([url]) => String(url) === '/api/model-versions/2/approve')
  expect(JSON.parse(String(approveCall?.[1]?.body))).toEqual({ role: 'director' })
})

test('a refused approval shows why and keeps the version proposed', async () => {
  backend({
    'GET /api/model-versions': () => json([version({})]),
    'POST /api/calibration/run': () => json(calibration),
    'POST /api/model-versions/2/approve': () =>
      json({ error: { code: 'decision_refused', message: 'A model version is approved by Planning, the Director or the Incident Commander.' } }, 403),
  })

  render(<CalibrationPage />)
  await userEvent.click(await screen.findByRole('button', { name: /run the back-test/i }))
  await userEvent.selectOptions(await screen.findByLabelText(/deciding as/i), 'logistics')
  await userEvent.click(screen.getByRole('button', { name: /approve model version 2/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/approved by planning, the director/i)
  expect(screen.getByRole('button', { name: /approve model version 2/i })).toBeEnabled()
})
