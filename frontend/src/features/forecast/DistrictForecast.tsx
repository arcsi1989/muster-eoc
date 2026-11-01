import { formatCustomersShort, formatSpread } from '../../lib/format'
import type { LoadState } from '../../lib/useLoad'
import type { OutageForecast } from '../../types/scenario'

interface PanelProps {
  state: LoadState<OutageForecast>
  /** the last loaded forecast, kept on screen while the next advisory's loads */
  shown?: OutageForecast | null
  onRetry: () => void
}

/** The forecast's load states around the table (F3). */
export function ForecastPanel({ state, shown, onRetry }: PanelProps) {
  if (state.status === 'error')
    return (
      <div role="alert">
        <p className="error-text">Could not load the outage forecast: {state.error.message}</p>
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  const forecast = state.status === 'ok' ? state.data : shown
  if (forecast) return <DistrictForecastTable forecast={forecast} />
  if (state.status === 'idle') return <p className="hint">Issue advisory 1 to see the outage forecast.</p>
  return <p className="hint">Loading the outage forecast…</p>
}

/** Customers out and crews and generators needed against available, per district, as P50–P90. */
export function DistrictForecastTable({ forecast }: { forecast: OutageForecast }) {
  if (forecast.districts.length === 0) return <p className="hint">No forecast for advisory {forecast.advisory_no}.</p>
  return (
    <div className="district-forecast">
      <table className="lineage" aria-label={`Outage forecast by district, advisory ${forecast.advisory_no}`}>
        <thead>
          <tr>
            <th scope="col">District</th>
            <th scope="col">Customers out</th>
            <th scope="col">Crews / have</th>
            <th scope="col">Gen&shy;erators</th>
          </tr>
        </thead>
        <tbody>
          {forecast.districts.map((d) => {
            const short = d.crews_needed.p90 > d.crews_available
            return (
              <tr key={d.district}>
                <th scope="row">{d.district}</th>
                <td>
                  <span className="figure-line">power {formatSpread(d.power_customers, formatCustomersShort)}</span>{' '}
                  <span className="figure-line">water {formatSpread(d.water_customers, formatCustomersShort)}</span>
                </td>
                <td>
                  <span className="figure-line">
                    {formatSpread(d.crews_needed)} / {d.crews_available}
                  </span>{' '}
                  {short && <span className="badge status-overridden">short</span>}
                </td>
                <td>{formatSpread(d.generators_needed)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="hint small">
        Customers out and crews and generators needed, median–P90 over{' '}
        {forecast.samples.toLocaleString('en-US')} ensemble samples, the open playbook actions included. Short: the
        P90 needs more crews than the district&apos;s staging areas have. {forecast.generators_available} fuelled
        generators serve the whole territory. A forecast from the risk model, not a decision.
      </p>
    </div>
  )
}
