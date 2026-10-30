/** 12,345 customer-equivalents as "12.3k". */
export function formatCustomers(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)
}

/** 0.284 as "28%". */
export const formatPercent = (p: number) => `${Math.round(p * 100)}%`

/** "Top-10% capture" (the top decile) for a fraction of 0.10; built from it so it follows the config. */
export const captureLabel = (topFraction: number) => `Top-${formatPercent(topFraction)} capture`

const clockOptions: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }
const clock = new Intl.DateTimeFormat('en-GB', clockOptions)
const clockSeconds = new Intl.DateTimeFormat('en-GB', { ...clockOptions, second: '2-digit' })

/** When something happened, in the browser's time zone: "30 Oct, 09:15" (or "09:15:42"). */
export const formatWallClock = (iso: string, { seconds = false } = {}) =>
  (seconds ? clockSeconds : clock).format(new Date(iso))
