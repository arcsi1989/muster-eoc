import { formatCustomers, formatSpread } from '../../lib/format'
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
            <th scope="col">Power customers out</th>
            <th scope="col">Water customers out</th>
            <th scope="col">Crews needed / available</th>
            <th scope="col">Generators needed</th>
          </tr>
        </thead>
        <tbody>
          {forecast.districts.map((d) => {
            const short = d.crews_needed.p90 > d.crews_available
            return (
              <tr key={d.district}>
                <th scope="row">{d.district}</th>
                <td>{formatSpread(d.power_customers, formatCustomers)}</td>
                <td>{formatSpread(d.water_customers, formatCustomers)}</td>
                <td>
                  {formatSpread(d.crews_needed)} / {d.crews_available}
                  {short && <span className="badge status-overridden"> short at P90</span>}
                </td>
                <td>{formatSpread(d.generators_needed)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="hint small">
        Median–P90 over {forecast.samples.toLocaleString('en-US')} ensemble samples. Needs include the open playbook
        actions; {forecast.generators_available} fuelled generators serve the whole territory. A forecast from the risk
        model, not a decision.
      </p>
    </div>
  )
}
