/** Green (0) through amber to red (1) for a score in [0, 1]. */
export function riskColor(score: number): string {
  const s = Math.min(1, Math.max(0, score))
  const hue = Math.round(120 * (1 - s))
  return `hsl(${hue} 75% 42%)`
}
