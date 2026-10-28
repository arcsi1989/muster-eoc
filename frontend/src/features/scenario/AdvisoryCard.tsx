import { formatDelta, formatIssuedAt, LEVEL_LABEL } from '../../lib/labels'
import type { Advisory } from '../../types/scenario'

interface Props {
  advisory: Advisory
  previous: Advisory | undefined
}

export function AdvisoryCard({ advisory, previous }: Props) {
  const wind = formatDelta(previous ? advisory.max_wind_mph - previous.max_wind_mph : null, 'mph')
  const surge = formatDelta(previous ? advisory.peak_surge_m - previous.peak_surge_m : null, 'm', 1)

  return (
    <section className="card" aria-label={`Advisory ${advisory.advisory_no}`}>
      <p className="eyebrow">
        Advisory {advisory.advisory_no} · issued {formatIssuedAt(advisory.issued_at)}
      </p>
      <p className="headline">
        {advisory.hours_to_landfall} h to landfall
        {advisory.activation_level && (
          <span className={`badge badge-${advisory.activation_level}`}>{LEVEL_LABEL[advisory.activation_level]}</span>
        )}
      </p>
      <dl className="facts">
        <div>
          <dt>Max wind</dt>
          <dd>
            {advisory.max_wind_mph} mph {wind && <span className="delta">({wind})</span>}
          </dd>
        </div>
        <div>
          <dt>Peak surge</dt>
          <dd>
            {advisory.peak_surge_m.toFixed(1)} m {surge && <span className="delta">({surge})</span>}
          </dd>
        </div>
      </dl>
    </section>
  )
}
