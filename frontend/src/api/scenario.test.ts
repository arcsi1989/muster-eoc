import { afterEach, expect, test, vi } from 'vitest'
import { ApiError } from './client'
import {
  approveModelVersion,
  getAlerts,
  getForecast,
  getAudit,
  getExplanation,
  getExposure,
  getLineage,
  getModelVersions,
  getRisk,
  nextAdvisory,
  postDeclaration,
  runCalibration,
  streamChat,
} from './scenario'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

test('nextAdvisory posts to the proxied advisories endpoint', async () => {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(json({ total_advisories: 5, current_advisory: 1, advisories: [] }))

  const scenario = await nextAdvisory()

  expect(fetchMock).toHaveBeenCalledWith('/api/advisories/next', expect.objectContaining({ method: 'POST' }))
  expect(scenario.current_advisory).toBe(1)
})

test('postDeclaration posts the declared level, the role and the reason', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ advisory_no: 3, activation_level: 'full' }))

  const pkg = await postDeclaration({ level: 'full', declared_by: 'incident_commander', reason: 'on track' })

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/activation/declare',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ level: 'full', declared_by: 'incident_commander', reason: 'on track' }),
    }),
  )
  expect(pkg.activation_level).toBe('full')
})

test('getRisk asks for the given advisory', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ advisory_no: 2, model_version: 1, items: [] }))

  await getRisk(2)

  expect(fetchMock).toHaveBeenCalledWith('/api/risk?advisory=2', expect.anything())
})

test('getForecast asks for the given advisory', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    json({ advisory_no: 3, model_version: 1, samples: 1000, generators_available: 6, districts: [] }),
  )

  await getForecast(3)

  expect(fetchMock).toHaveBeenCalledWith('/api/forecast?advisory=3', expect.anything())
})

test('an error response becomes an ApiError with the backend code and message', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    json({ error: { code: 'scenario_complete', message: 'all 5 advisories have been issued' } }, 409),
  )

  const error = await nextAdvisory().catch((e: unknown) => e)

  expect(error).toBeInstanceOf(ApiError)
  expect(error).toMatchObject({ status: 409, code: 'scenario_complete', message: 'all 5 advisories have been issued' })
})

test('getLineage reads the data quality report', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json([]))

  expect(await getLineage()).toEqual([])
  expect(fetchMock).toHaveBeenCalledWith('/api/lineage', expect.anything())
})

test('getExposure asks for the given advisory', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json([]))

  await getExposure(3)

  expect(fetchMock).toHaveBeenCalledWith('/api/exposure?advisory=3', expect.anything())
})

test('getExplanation and getAlerts ask for the given asset and advisory', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => json([]))

  await getExplanation('SUB-07', 3)
  await getAlerts(4)

  expect(fetchMock).toHaveBeenCalledWith('/api/assets/SUB-07/explain?advisory=3', expect.anything())
  expect(fetchMock).toHaveBeenCalledWith('/api/alerts?advisory=4', expect.anything())
})

test('getAudit asks for everyone or one actor', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => json([]))

  await getAudit()
  await getAudit('agent')

  expect(fetchMock).toHaveBeenCalledWith('/api/audit', expect.anything())
  expect(fetchMock).toHaveBeenCalledWith('/api/audit?actor=agent', expect.anything())
})

test('runCalibration posts to the calibration run endpoint', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ storm: 'Storm Delta' }))

  expect(await runCalibration()).toMatchObject({ storm: 'Storm Delta' })
  expect(fetchMock).toHaveBeenCalledWith('/api/calibration/run', expect.objectContaining({ method: 'POST' }))
})

test('getModelVersions reads the model versions', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json([]))

  expect(await getModelVersions()).toEqual([])
  expect(fetchMock).toHaveBeenCalledWith('/api/model-versions', expect.anything())
})

test('approveModelVersion posts the role to the version it approves', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ id: 2, status: 'approved' }))

  await approveModelVersion(2, 'planning')

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/model-versions/2/approve',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ role: 'planning' }) }),
  )
})

/** A server-sent event stream that arrives in the given chunks. */
function sse(...chunks: string[]) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } })
}

const step = (kind: string, tool: string | null = null) =>
  `event: step\ndata: ${JSON.stringify({ kind, attempt: 1, provider: 'template', problems: [], reason: null, tool, args: {} })}\n\n`

test('streamChat reports each step as it arrives and resolves with the answer', async () => {
  const answer = `event: answer\ndata: ${JSON.stringify({ answer: 'SUB-07 supports HOSP-01.', citations: [] })}\n\n`
  const whole = step('attempt') + step('tool_call', 'get_dependencies') + answer
  // split mid-event, so a step only counts once its block is complete
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(sse(whole.slice(0, 50), whole.slice(50)))
  const steps: string[] = []

  const reply = await streamChat('What depends on SUB-07?', [], (s) => steps.push(s.tool ?? s.kind))

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/copilot/chat/stream',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ message: 'What depends on SUB-07?', history: [] }) }),
  )
  expect(steps).toEqual(['attempt', 'get_dependencies'])
  expect(reply.answer).toBe('SUB-07 supports HOSP-01.')
})

test('streamChat rejects with the error event of the stream', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    sse(step('attempt'), `event: error\ndata: ${JSON.stringify({ error: { code: 'internal', message: 'the copilot could not answer' } })}\n\n`),
  )

  await expect(streamChat('Hi', [], () => {})).rejects.toMatchObject({ code: 'internal', message: 'the copilot could not answer' })
})

test('streamChat rejects with the error body of a refused request', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ error: { code: 'validation_error', message: 'message: too short' } }, 422))

  await expect(streamChat('', [], () => {})).rejects.toBeInstanceOf(ApiError)
})
