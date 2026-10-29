import { useCallback } from 'react'
import { getExplanation } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'
import { ExplainPanel } from './ExplainPanel'

interface Props {
  assetId: string
  advisoryNo: number
  onClose: () => void
}

export function ExplainDrawer({ assetId, advisoryNo, onClose }: Props) {
  const loader = useCallback(() => getExplanation(assetId, advisoryNo), [assetId, advisoryNo])
  const { state, retry } = useLoad(loader)
  const title = state.status === 'ok' ? `${assetId} ${state.data.asset.name}` : assetId

  return (
    <aside className="drawer" aria-label={`Why ${assetId} ranks where it does`}>
      <div className="drawer-head">
        <h2>{title}</h2>
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
      {state.status === 'loading' && <p className="hint">Loading the explanation…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the explanation: {state.error.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && <ExplainPanel explanation={state.data} />}
    </aside>
  )
}
