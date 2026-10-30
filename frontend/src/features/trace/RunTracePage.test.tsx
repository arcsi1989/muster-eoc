import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { Scenario } from '../../types/scenario'
import { RunTracePage } from './RunTracePage'
import { makeSpan, makeTotals, makeTrace } from './traceFixtures'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const scenario = (current: number): Scenario => ({
  total_advisories: 5,
  current_advisory: current,
  timeline: [],
  advisories: [],
})

/** Answers GET requests by path; a route may answer differently on each call. */
function backend(routes: Record<string, () => Response>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const route = routes[String(input)]
    if (!route) throw new Error(`unexpected request ${String(input)}`)
    return route()
  })
}

const llmTrace = makeTrace({
  spans: [
    makeSpan({ span_id: 'n1', node: 'ingest' }, 0, 100),
    makeSpan({ span_id: 'n2', node: 'draft' }, 100, 1900),
    makeSpan(
      {
        span_id: 'g1',
        parent_span_id: 'n2',
        kind: 'generation',
        node: 'sitrep_draft',
        provider: 'template (fallback)',
        model: 'claude-sonnet-5-5',
        tokens_in: 2400,
        tokens_out: 610,
        cost_usd: 0.0164,
        retries: 1,
        fallback: true,
        fallback_reason: 'draft rejected: cites PS-99, not in the findings',
        validation: 'failed',
        attempts: [
          { model: 'claude-sonnet-5-5', problems: ['cites PS-99, not in the findings'] },
          { model: 'claude-sonnet-5-5', problems: ['cites PS-99, not in the findings'] },
        ],
      },
      200,
      1600,
    ),
    makeSpan({ span_id: 'n3', node: 'await_approval', status: 'paused' }, 2000, 0),
  ],
  advisory_totals: makeTotals({ latency_ms: 2000, tokens_in: 2400, tokens_out: 610, cost_usd: 0.0164, retries: 1, fallbacks: 1 }),
  run_totals: makeTotals({ latency_ms: 5300, tokens_in: 7100, tokens_out: 1500, cost_usd: 0.0441, retries: 1, fallbacks: 1 }),
})

test('the waterfall shows each span as a duration bar, a generation under its node', async () => {
  backend({ '/api/advisories': () => json(scenario(3)), '/api/advisories/3/trace': () => json(llmTrace) })

  render(<RunTracePage />)

  const waterfall = await screen.findByRole('table', { name: /waterfall/i })
  const rows = within(waterfall).getAllByRole('row').slice(1)
  expect(rows.map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual([
    'ingest',
    'draft',
    'sitrep_draft',
    'await_approval',
  ])
  const bar = within(rows[1]).getByRole('img', { name: /draft: 1\.9 s/i })
  expect(bar).toHaveStyle({ left: '5%', width: '95%' })
  expect(within(rows[2]).getAllByRole('cell')[0]).toHaveClass('trace-depth-1')
  expect(within(rows[3]).getByText(/paused for decisions/i)).toBeInTheDocument()
})

test('model, tokens and cost per span; a retry and the template fallback are highlighted', async () => {
  backend({ '/api/advisories': () => json(scenario(3)), '/api/advisories/3/trace': () => json(llmTrace) })

  render(<RunTracePage />)

  const generation = (await screen.findByText('sitrep_draft')).closest('tr')!
  expect(generation).toHaveClass('trace-highlight')
  expect(within(generation).getByText('claude-sonnet-5-5')).toBeInTheDocument()
  expect(within(generation).getByText('2,400 in / 610 out')).toBeInTheDocument()
  expect(within(generation).getByText('$0.0164')).toBeInTheDocument()
  expect(within(generation).getByText('1 retry')).toBeInTheDocument()
  expect(within(generation).getByText('Template fallback')).toBeInTheDocument()
  expect(within(generation).getByText(/cites PS-99, not in the findings/, { selector: '.trace-reason' })).toBeInTheDocument()

  const ingest = screen.getByText('ingest').closest('tr')!
  expect(ingest).not.toHaveClass('trace-highlight')
  expect(within(ingest).getByText('$0')).toBeInTheDocument()
})

test('totals for the advisory and for the demo run', async () => {
  backend({ '/api/advisories': () => json(scenario(3)), '/api/advisories/3/trace': () => json(llmTrace) })

  render(<RunTracePage />)

  const totals = await screen.findByRole('table', { name: /totals/i })
  const cells = (label: string) =>
    within(within(totals).getByRole('rowheader', { name: label }).closest('tr')!)
      .getAllByRole('cell')
      .map((c) => c.textContent)
  expect(cells('Latency')).toEqual(['2.0 s', '5.3 s'])
  expect(cells('Tokens')).toEqual(['2,400 in / 610 out', '7,100 in / 1,500 out'])
  expect(cells('Estimated cost')).toEqual(['$0.0164', '$0.0441'])
  expect(cells('Retries')).toEqual(['1', '1'])
  expect(cells('Template fallbacks')).toEqual(['1', '1'])
})

test('a token count from a model with no price is said, not guessed', async () => {
  const trace = makeTrace({
    spans: [makeSpan({ span_id: 'g', node: 'copilot', kind: 'generation', model: 'local-model', tokens_in: 50, cost_usd: null })],
    advisory_totals: makeTotals({ unpriced_spans: 1 }),
    run_totals: makeTotals({ unpriced_spans: 1 }),
  })
  backend({ '/api/advisories': () => json(scenario(3)), '/api/advisories/3/trace': () => json(trace) })

  render(<RunTracePage />)

  expect(await screen.findByText('no price')).toBeInTheDocument()
  expect(screen.getAllByText(/1 span with tokens but no price/)).toHaveLength(2)
})

test('the trace of any issued advisory can be opened', async () => {
  const fetch = backend({
    '/api/advisories': () => json(scenario(3)),
    '/api/advisories/3/trace': () => json(llmTrace),
    '/api/advisories/1/trace': () =>
      json(makeTrace({ advisory_no: 1, spans: [makeSpan({ span_id: 'x', node: 'issue', advisory_no: 1 })] })),
  })

  render(<RunTracePage />)
  await screen.findByText('sitrep_draft')
  await userEvent.click(screen.getByRole('button', { name: 'Advisory 1' }))

  expect(await screen.findByText('issue')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Advisory 1' })).toHaveAttribute('aria-pressed', 'true')
  expect(fetch).toHaveBeenCalledWith('/api/advisories/1/trace', expect.anything())
})

test('empty states: before advisory 1, and an advisory with no spans', async () => {
  backend({ '/api/advisories': () => json(scenario(0)) })
  const { unmount } = render(<RunTracePage />)
  expect(await screen.findByText(/no advisory issued yet/i)).toBeInTheDocument()
  unmount()
  vi.restoreAllMocks()

  backend({ '/api/advisories': () => json(scenario(2)), '/api/advisories/2/trace': () => json(makeTrace({ advisory_no: 2 })) })
  render(<RunTracePage />)
  expect(await screen.findByText(/no spans recorded for advisory 2/i)).toBeInTheDocument()
})

test('a failed load says so and retries', async () => {
  let calls = 0
  backend({
    '/api/advisories': () => json(scenario(3)),
    '/api/advisories/3/trace': () =>
      ++calls === 1 ? json({ error: { code: 'internal', message: 'Trace store unavailable' } }, 500) : json(llmTrace),
  })

  render(<RunTracePage />)

  expect(await screen.findByText(/could not load the run trace: trace store unavailable/i)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('sitrep_draft')).toBeInTheDocument()
})

test('a loading state while the trace loads', async () => {
  backend({ '/api/advisories': () => json(scenario(3)), '/api/advisories/3/trace': () => json(llmTrace) })
  render(<RunTracePage />)
  expect(await screen.findByText(/loading the run trace/i)).toBeInTheDocument()
  await screen.findByText('sitrep_draft')
})

test('refresh loads the spans recorded since, such as a copilot turn', async () => {
  let calls = 0
  backend({
    '/api/advisories': () => json(scenario(3)),
    '/api/advisories/3/trace': () =>
      json(
        ++calls === 1
          ? llmTrace
          : { ...llmTrace, spans: [...llmTrace.spans, makeSpan({ span_id: 't', node: 'copilot', kind: 'generation' }, 9000)] },
      ),
  })

  render(<RunTracePage />)
  await screen.findByText('sitrep_draft')
  expect(screen.queryByText('copilot')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))

  expect(await screen.findByText('copilot')).toBeInTheDocument()
})
