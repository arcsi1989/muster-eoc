import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import { getPackage, postDecision } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { Asset, DecisionAction, PackageItem, Role } from '../../types/scenario'
import { PackageView } from './PackageView'

interface Props {
  advisoryNo: number
  role: Role
  assetsById: Map<string, Asset>
}

export function PackagePanel({ advisoryNo, role, assetsById }: Props) {
  const loader = useCallback(() => getPackage(advisoryNo), [advisoryNo])
  const { state, retry, setData } = useLoad(advisoryNo > 0 ? loader : null)
  const [error, setError] = useState<{ advisoryNo: number; itemId: number; error: ApiError } | null>(null)
  const [busy, setBusy] = useState(false)

  async function onDecide(item: PackageItem, action: DecisionAction, reason?: string) {
    setError(null)
    setBusy(true)
    try {
      setData(await postDecision(advisoryNo, item.id, { role, action, reason }))
    } catch (e) {
      const apiError = toApiError(e)
      setError({ advisoryNo, itemId: item.id, error: apiError })
      if (apiError.code === 'package_closed' || apiError.code === 'already_decided') retry()
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card" aria-label="Decision package">
      <h2>Decision package</h2>
      {state.status === 'idle' && <p className="hint">Issue advisory 1 to receive the first decision package.</p>}
      {state.status === 'loading' && <p className="hint">Loading the decision package…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the decision package: {state.error.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && (
        <PackageView
          pkg={state.data}
          assetsById={assetsById}
          error={error?.advisoryNo === advisoryNo ? error : null}
          busy={busy}
          onDecide={onDecide}
        />
      )}
    </section>
  )
}
