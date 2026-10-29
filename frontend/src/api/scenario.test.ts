import { afterEach, expect, test, vi } from 'vitest'
import { ApiError } from './client'
import { getAlerts, getAudit, getExplanation, getExposure, getLineage, getRisk, nextAdvisory, postDeclaration } from './scenario'

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
