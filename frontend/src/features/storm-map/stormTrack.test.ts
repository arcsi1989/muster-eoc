import { expect, test } from 'vitest'
import type { TrackPoint } from '../../types/scenario'
import { formatLocalTime, timeLabels } from './stormTrack'

const point = (t_hours: number, x_km: number, y_km: number): TrackPoint => ({
  t_hours,
  x_km,
  y_km,
  valid_at: new Date(Date.UTC(2026, 8, 3, 3) + t_hours * 3_600_000).toISOString(),
  vmax_mph: 130,
  category: 'cat_4',
  rmax_km: 37,
})

const BOX = { width: 60, height: 14 }

test('local time reads like an NHC label: hour and weekday', () => {
  // 3 Sept 2026 is a Thursday; 11:00 UTC is 07:00 at UTC-4
  expect(formatLocalTime('2026-09-03T11:00:00Z')).toBe('07:00 Thu')
  expect(formatLocalTime('2026-09-03T03:00:00Z')).toBe('23:00 Wed')
})

test('only the 12-hour points get a label', () => {
  const track = [0, 6, 12, 18, 24, 30, 36].map((t) => point(t, 0, t * 15))

  expect(timeLabels(track, BOX).map((p) => p.t_hours)).toEqual([0, 12, 24, 36])
})

test('labels that would collide are thinned to every other one', () => {
  const close = [0, 12, 24, 36, 48].map((t) => point(t, 0, t))

  expect(timeLabels(close, BOX).map((p) => p.t_hours)).toEqual([0, 24, 48])
})

test('labels apart on either axis do not collide', () => {
  const sideways = [0, 12, 24].map((t) => point(t, t * 6, 0))

  expect(timeLabels(sideways, BOX)).toHaveLength(3)
})
