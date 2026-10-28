import type { ActivationLevel } from '../types/scenario'

export const LEVEL_LABEL: Record<ActivationLevel, string> = {
  monitor: 'Monitor',
  prepare: 'Prepare',
  full: 'Full activation',
}

const issuedFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'UTC',
})

/** "2 Sept, 03:00 UTC" */
export const formatIssuedAt = (iso: string) => `${issuedFormat.format(new Date(iso))} UTC`

/** "+5", "−0.5", "±0" with a unit; null when there is nothing to compare with. */
export function formatDelta(value: number | null, unit: string, digits = 0): string | null {
  if (value === null) return null
  if (value === 0) return `±0 ${unit}`
  const sign = value > 0 ? '+' : '−'
  return `${sign}${Math.abs(value).toFixed(digits)} ${unit}`
}
