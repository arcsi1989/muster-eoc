/** Failure probability at which the colour is fully red. */
export const FULL_RED_AT = 0.5

/** Green (0) through amber to red (FULL_RED_AT and above) for a failure probability. */
export function pFailColor(pFail: number): string {
  const s = Math.min(1, Math.max(0, pFail / FULL_RED_AT))
  const hue = Math.round(120 * (1 - s))
  return `hsl(${hue} 75% 42%)`
}
