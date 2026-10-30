import type { ChallengerFeature } from '../../types/scenario'

/** The challenger's features (backend muster/challenger/dataset.py FEATURES), as a person reads them. */
const FEATURE_LABEL: Record<string, string> = {
  wind_p50_mph: 'Wind P50',
  wind_p90_mph: 'Wind P90',
  flood_p50_m: 'Flood P50',
  flood_p90_m: 'Flood P90',
  condition_score: 'Condition score',
  age_years: 'Age',
  asset_type: 'Asset type',
  elevation_imputed: 'Elevation imputed',
  distance_to_coast_km: 'Distance to coast',
  critical_dependency: 'Feeds a critical facility',
}

const UNIT: Record<string, string> = {
  wind_p50_mph: ' mph',
  wind_p90_mph: ' mph',
  flood_p50_m: ' m',
  flood_p90_m: ' m',
  age_years: ' years',
  distance_to_coast_km: ' km',
}

const YES_NO = new Set(['elevation_imputed', 'critical_dependency'])

function formatValue({ feature, value }: ChallengerFeature): string {
  if (typeof value === 'string') return value.replaceAll('_', ' ')
  if (YES_NO.has(feature)) return value ? 'yes' : 'no'
  if (feature === 'condition_score') return `${value}/5`
  return `${Number(value.toFixed(feature.startsWith('flood') ? 2 : 0))}${UNIT[feature] ?? ''}`
}

/** "+12 pts": how much the feature raises (or lowers) the challenger's failure probability. */
function formatContribution(c: number): string {
  const points = Math.round(c * 100)
  if (points === 0) return '±0 pts'
  return `${points > 0 ? '+' : '−'}${Math.abs(points)} pts`
}

/** The challenger's top features for an asset, the largest push upward first. */
export function ChallengerFeatures({ features, label }: { features: ChallengerFeature[]; label: string }) {
  return (
    <ol className="challenger-features small" aria-label={label}>
      {features.map((f) => (
        <li key={f.feature}>
          <span>
            {FEATURE_LABEL[f.feature] ?? f.feature} {formatValue(f)}
          </span>{' '}
          <span className="hint">{formatContribution(f.contribution)}</span>
        </li>
      ))}
    </ol>
  )
}
