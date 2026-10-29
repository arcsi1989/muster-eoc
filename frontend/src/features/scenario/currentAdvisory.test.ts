import { expect, test } from 'vitest'
import type { Advisory, Scenario } from '../../types/scenario'
import { currentAdvisories } from './currentAdvisory'

const advisory = (no: number): Advisory => ({
  advisory_no: no,
  issued_at: '2026-10-01T00:00:00Z',
  hours_to_landfall: 84 - 12 * no,
  activation_level: 'prepare',
  max_wind_mph: 100,
  peak_surge_m: 2,
  landfall: { x_km: 0, y_km: 0 },
  track: [],
  cone: [],
})

const scenario = (current: number, issued: number[]): Scenario => ({
  total_advisories: 5,
  current_advisory: current,
  timeline: [],
  advisories: issued.map(advisory),
})

test('before advisory 1 there is no current advisory', () => {
  expect(currentAdvisories(scenario(0, []))).toEqual({ currentNo: 0, current: undefined, previous: undefined })
})

test('while the scenario loads there is no current advisory', () => {
  expect(currentAdvisories(null)).toEqual({ currentNo: 0, current: undefined, previous: undefined })
})

test('the current advisory is the one the backend names, not the last in the list', () => {
  const { currentNo, current, previous } = currentAdvisories(scenario(2, [1, 2, 3]))

  expect(currentNo).toBe(2)
  expect(current?.advisory_no).toBe(2)
  expect(previous?.advisory_no).toBe(1)
})

test('at advisory 1 there is no previous advisory', () => {
  const { current, previous } = currentAdvisories(scenario(1, [1]))

  expect(current?.advisory_no).toBe(1)
  expect(previous).toBeUndefined()
})
