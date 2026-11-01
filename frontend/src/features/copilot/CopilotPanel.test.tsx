import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { ChatReply, CopilotStep, CopilotWork } from '../../types/scenario'
import { CopilotPanel } from './CopilotPanel'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const WORK: CopilotWork = {
  tool_calls: [{ name: 'explain_score', args: { asset_id: 'PS-14', advisory: null }, result: { asset_id: 'PS-14', rank: 106 } }],
  attempts: [
    { provider: 'template', model: null, prompt_version: null, latency_ms: 0, input_tokens: 0, output_tokens: 0, problems: [], error: null },
  ],
  retries: 0,
  validated: true,
  provider: 'template',
  model: null,
  prompt_version: null,
  input_tokens: 0,
  output_tokens: 0,
  cost_usd: 0,
  fallback: false,
  fallback_reason: null,
}

const reply = (overrides: Partial<ChatReply> = {}): ChatReply => ({
  answer: 'PS-14 Seawall Pumping Station is ranked 106 at advisory 3; stop-work P-4.7 applies from advisory 5.',
  citations: [
    { id: 'PS-14', kind: 'asset' },
    { id: 'P-4.7', kind: 'clause' },
  ],
  provider: 'template',
  fallback: false,
  tools_used: ['explain_score'],
  advisory: 3,
  work: WORK,
  ...overrides,
})

const step = (kind: CopilotStep['kind'], extra: Partial<CopilotStep> = {}): CopilotStep => ({
  kind,
  attempt: 1,
  provider: 'template',
  problems: [],
  reason: null,
  tool: null,
  args: {},
  ...extra,
})

const encoder = new TextEncoder()
const frame = (event: string, data: unknown) => encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)

/** A stream the test feeds event by event, to see what the panel shows while the turn runs. */
function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) })
  return {
    response: new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }),
    send: (event: string, data: unknown) => controller.enqueue(frame(event, data)),
    close: () => controller.close(),
  }
}

/** A finished stream: the given steps, then the answer. */
function streamOf(steps: CopilotStep[], answer: ChatReply) {
  const s = controlledStream()
  for (const st of steps) s.send('step', st)
  s.send('answer', answer)
  s.close()
  return s.response
}

function mockApi(chat: (body: { message: string; history: unknown[] }) => Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (String(input).endsWith('/clauses')) {
      return json([{ id: 'P-4.7', section: '4', title: 'Stop-work on wind (always in force)', text: 'No field work at a site where tropical-storm-force wind is forecast within 12 hours.' }])
    }
    return chat(JSON.parse(String(init?.body)))
  })
}

test('a suggested question gets an answer with clickable citations', async () => {
  mockApi(() => streamOf([], reply()))
  const onSelectAsset = vi.fn()
  render(<CopilotPanel onSelectAsset={onSelectAsset} />)

  await userEvent.click(screen.getByRole('button', { name: 'Why is PS-14 ranked where it is?' }))

  expect(await screen.findByText(/ranked 106 at advisory 3/)).toBeInTheDocument()
  expect(screen.getByText(/Offline answer · advisory 3 · tools: explain_score/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'PS-14' }))
  expect(onSelectAsset).toHaveBeenCalledWith('PS-14')
  await userEvent.click(screen.getByRole('button', { name: 'P-4.7' }))
  expect(screen.getByRole('complementary', { name: 'Clause P-4.7' })).toHaveTextContent('No field work')
})

test('each step shows while the turn runs, and the answer only once it arrives validated', async () => {
  const stream = controlledStream()
  mockApi(() => stream.response)
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.click(screen.getByRole('button', { name: 'Why is PS-14 ranked where it is?' }))
  stream.send('step', step('attempt', { provider: 'anthropic' }))
  stream.send('step', step('tool_call', { provider: 'anthropic', tool: 'explain_score', args: { asset_id: 'PS-14', advisory: null } }))
  stream.send('step', step('validating', { provider: 'anthropic' }))
  stream.send('step', step('rejected', { provider: 'anthropic', problems: ['it states numbers no tool returned: 12,000'] }))
  stream.send('step', step('fallback', { provider: 'template (fallback)', reason: 'the answer was not grounded' }))

  const progress = await screen.findByRole('status', { name: 'Copilot progress' })
  expect(await within(progress).findByText(/Falling back to the template: the answer was not grounded/)).toBeInTheDocument()
  expect(within(progress).getByText('Asking anthropic')).toBeInTheDocument()
  expect(within(progress).getByText('Called explain_score(asset_id: "PS-14", advisory: current)')).toBeInTheDocument()
  expect(within(progress).getByText('Rejected: it states numbers no tool returned: 12,000')).toBeInTheDocument()
  expect(screen.queryByText(/ranked 106/)).not.toBeInTheDocument()

  stream.send('answer', reply({ provider: 'template (fallback)', fallback: true }))
  stream.close()

  expect(await screen.findByText(/ranked 106 at advisory 3/)).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: 'Copilot progress' })).not.toBeInTheDocument()
})

test('each answer has a "How I got this" panel with the tools, validation and cost', async () => {
  const work: CopilotWork = {
    ...WORK,
    attempts: [
      { provider: 'anthropic', model: 'claude-sonnet-5-5', prompt_version: 'copilot-v2', latency_ms: 2100, input_tokens: 1200, output_tokens: 90, problems: ['it names IDs no tool returned: SUB-99'], error: null },
      { provider: 'anthropic', model: 'claude-sonnet-5-5', prompt_version: 'copilot-v2', latency_ms: 1900, input_tokens: 1300, output_tokens: 80, problems: [], error: null },
    ],
    retries: 1,
    provider: 'anthropic',
    model: 'claude-sonnet-5-5',
    prompt_version: 'copilot-v2',
    input_tokens: 2500,
    output_tokens: 170,
    cost_usd: 0.0067,
  }
  mockApi(() => streamOf([step('attempt', { provider: 'anthropic' })], reply({ provider: 'anthropic', work })))
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.click(screen.getByRole('button', { name: 'Why is PS-14 ranked where it is?' }))
  await userEvent.click(await screen.findByText('How I got this'))

  const panel = screen.getByText('How I got this').closest('details') as HTMLElement
  expect(panel).toHaveAttribute('open')
  expect(within(panel).getByText('anthropic · claude-sonnet-5-5')).toBeInTheDocument()
  expect(within(panel).getByText('copilot-v2')).toBeInTheDocument()
  expect(within(panel).getByText('Passed: every ID and number came from a tool')).toBeInTheDocument()
  expect(within(panel).getByText('2,500 in · 170 out')).toBeInTheDocument()
  expect(within(panel).getByText('$0.0067 (estimate)')).toBeInTheDocument()
  expect(within(panel).getByText(/rejected: it names IDs no tool returned: SUB-99/)).toBeInTheDocument()
  expect(within(panel).getByText('explain_score(asset_id: "PS-14", advisory: current)')).toBeInTheDocument()
  expect(within(panel).getByText(/"rank": 106/)).toBeInTheDocument()
  expect(within(panel).getByText('Asking anthropic')).toBeInTheDocument()
})

test('a template fallback says the answer was not validated and why', async () => {
  const work: CopilotWork = { ...WORK, validated: false, fallback: true, provider: 'template (fallback)', fallback_reason: 'the model call timed out' }
  mockApi(() => streamOf([], reply({ provider: 'template (fallback)', fallback: true, work })))
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.click(screen.getByRole('button', { name: 'Why is PS-14 ranked where it is?' }))
  await userEvent.click(await screen.findByText('How I got this'))

  expect(screen.getByText('The template (fallback)')).toBeInTheDocument()
  expect(screen.getByText('Not validated: the deterministic template answered instead')).toBeInTheDocument()
  expect(screen.getByText('the model call timed out')).toBeInTheDocument()
})

test('follow-up questions send the conversation so far', async () => {
  const fetchMock = mockApi(({ message }) =>
    streamOf([], reply({ answer: `Answer to ${message}`, citations: [], provider: 'anthropic', tools_used: [] })),
  )
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'First question')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await screen.findByText('Answer to First question')
  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'Second question')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await screen.findByText('Answer to Second question')

  const last = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/copilot/chat/stream')).at(-1)
  expect(JSON.parse(String(last?.[1]?.body)).history).toEqual([
    { role: 'user', content: 'First question' },
    { role: 'assistant', content: 'Answer to First question' },
  ])
  expect(screen.getAllByText('AI answer · advisory 3')).toHaveLength(2)
})

test('a failed request shows an error and keeps the question', async () => {
  mockApi(() => json({ error: { code: 'internal', message: 'database locked' } }, 500))
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'What are the top risks?')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  expect(screen.getByLabelText('Ask the copilot')).toHaveValue('What are the top risks?')
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
})

test('an error event in the stream shows as an error', async () => {
  const stream = controlledStream()
  mockApi(() => stream.response)
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.click(screen.getByRole('button', { name: 'What are the top risks?' }))
  stream.send('error', { error: { code: 'internal', message: 'the copilot could not answer' } })
  stream.close()

  expect(await screen.findByRole('alert')).toHaveTextContent('the copilot could not answer')
})
