import type { LoadState } from '../../lib/useLoad'
import type { Asset, RiskList as RiskListData } from '../../types/scenario'
import { RiskList } from './RiskList'

interface Props {
  state: LoadState<RiskListData>
  assetsById: Map<string, Asset>
  onRetry: () => void
}

export function RiskPanel({ state, assetsById, onRetry }: Props) {
  switch (state.status) {
    case 'idle':
      return <p className="hint">Issue advisory 1 to see the ranked risk list.</p>
    case 'loading':
      return <p className="hint">Loading the risk list…</p>
    case 'error':
      return (
        <div role="alert">
          <p className="error-text">Could not load the risk list: {state.error.message}</p>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )
    case 'ok':
      return <RiskList items={state.data.items} assetsById={assetsById} />
  }
}
