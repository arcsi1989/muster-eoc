import type { LoadState } from '../../lib/useLoad'
import type { Alert } from '../../types/scenario'

const KIND_LABEL: Record<Alert['kind'], string> = {
  risk_threshold: 'Threshold',
  top_n_entry: 'Entered top',
  rank_jump: 'Rank jump',
}

interface Props {
  state: LoadState<Alert[]>
  onRetry: () => void
  onSelect: (assetId: string) => void
}

export function AlertsPanel({ state, onRetry, onSelect }: Props) {
  return (
    <section className="card" aria-label="Alerts">
      <h2>Alerts</h2>
      {state.status === 'loading' && <p className="hint">Loading alerts…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load alerts: {state.error.message}</p>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && state.data.length === 0 && <p className="hint">No alerts for this advisory.</p>}
      {state.status === 'ok' && state.data.length > 0 && (
        <ul className="alerts">
          {state.data.map((alert) => (
            <li key={`${alert.asset_id}-${alert.kind}`}>
              <span className={`badge alert-${alert.kind}`}>{KIND_LABEL[alert.kind]}</span>{' '}
              <button type="button" className="link" onClick={() => onSelect(alert.asset_id)}>
                {alert.asset_id}
              </button>{' '}
              {alert.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
