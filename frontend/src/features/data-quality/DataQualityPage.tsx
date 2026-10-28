import { getLineage } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'
import { DataQualityTable } from './DataQualityTable'

export function DataQualityPage() {
  const { state, retry } = useLoad(getLineage)
  return (
    <main className="page">
      <h2>Data quality</h2>
      <p className="hint">
        Every gold file loaded at startup, checked row by row against its data contract. Rejected rows never reach
        the scores.
      </p>
      {state.status === 'loading' && <p className="hint">Loading the lineage…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the lineage: {state.error.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && <DataQualityTable entries={state.data} />}
    </main>
  )
}
