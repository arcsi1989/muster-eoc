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

/** 120 ms as "120 ms", 1900 ms as "1.9 s", 125000 ms as "2.1 min". */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60_000).toFixed(1)} min`
}

/** An estimated model cost in USD: "$0" for none, else four decimals ("$0.0164"). */
export const formatCost = (usd: number) => (usd === 0 ? '$0' : `$${usd.toFixed(4)}`)

/** Tokens sent and received: "2,400 in / 610 out". */
export const formatTokens = (tokensIn: number, tokensOut: number) =>
  `${tokensIn.toLocaleString('en-US')} in / ${tokensOut.toLocaleString('en-US')} out`

/** A count with its noun: "1 retry", "2 retries". */
export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
