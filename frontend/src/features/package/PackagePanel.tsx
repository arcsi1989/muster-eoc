import { useCallback, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { approveSitrep, getClauses, getPackage, postDecision } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { Asset, DecisionAction, PackageItem, Role } from '../../types/scenario'
import { PackageView } from './PackageView'

interface Props {
  advisoryNo: number
  role: Role
  assetsById: Map<string, Asset>
  onSelectAsset: (assetId: string) => void
}

const loadClauses = () => getClauses()

export function PackagePanel({ advisoryNo, role, assetsById, onSelectAsset }: Props) {
  const loader = useCallback(() => getPackage(advisoryNo), [advisoryNo])
  const { state, retry, setData } = useLoad(advisoryNo > 0 ? loader : null)
  const { state: clausesState, retry: retryClauses } = useLoad(loadClauses)
  const clauses = useMemo(
    () => new Map(clausesState.status === 'ok' ? clausesState.data.map((c) => [c.id, c]) : []),
    [clausesState],
  )
  const [error, setError] = useState<{ advisoryNo: number; itemId: number; error: ApiError } | null>(null)
  const [sitrepError, setSitrepError] = useState<{ advisoryNo: number; error: ApiError } | null>(null)
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

  async function onApproveSitrep(text: string) {
    setSitrepError(null)
    setBusy(true)
    try {
      await approveSitrep(advisoryNo, role, text)
      retry()
    } catch (e) {
      setSitrepError({ advisoryNo, error: toApiError(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card" aria-label="Decision package">
      <h2>Decision package</h2>
      {clausesState.status === 'error' && (
        <p role="alert" className="error-text small">
          Clause titles unavailable: {clausesState.error.message}{' '}
          <button type="button" className="link" onClick={retryClauses}>
            Retry
          </button>
        </p>
      )}
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
          sitrepOpen={state.data.advisory_no === advisoryNo}
          clauses={clauses}
          sitrepError={sitrepError?.advisoryNo === advisoryNo ? sitrepError.error : null}
          onApproveSitrep={onApproveSitrep}
          onSelectAsset={onSelectAsset}
        />
      )}
    </section>
  )
}
