/** 12,345 customer-equivalents as "12.3k". */
export function formatCustomers(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)
}

/** 0.284 as "28%". */
export const formatPercent = (p: number) => `${Math.round(p * 100)}%`
