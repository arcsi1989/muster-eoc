import { afterEach, expect, test, vi } from 'vitest'
import { ApiError } from './client'
import { getExposure, getLineage, getRisk, nextAdvisory } from './scenario'

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

test('getRisk asks for the given advisory', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ advisory_no: 2, items: [] }))

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
