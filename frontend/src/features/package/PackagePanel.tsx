import { useCallback, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { approveSitrep, getClauses, getPackage, postDecision, postDeclaration } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { ActivationLevel, Asset, DecisionAction, PackageItem, Role } from '../../types/scenario'
import { PackageView } from './PackageView'

interface Props {
  advisoryNo: number
  role: Role
  /** of the current advisory; null while the scenario is loading */
  hoursToLandfall: number | null
  assetsById: Map<string, Asset>
  onSelectAsset: (assetId: string) => void
  /** a level was declared: the scenario header shows it */
  onDeclared: () => void
}

const loadClauses = () => getClauses()

/** Errors that mean the package on screen is stale: reload it. */
const STALE_PACKAGE = new Set(['package_closed', 'already_decided', 'no_activation_proposal'])

/** An error is shown only while its advisory is the current one. */
interface AdvisoryError {
  advisoryNo: number
  error: ApiError
}

export function PackagePanel({ advisoryNo, role, hoursToLandfall, assetsById, onSelectAsset, onDeclared }: Props) {
  const loader = useCallback(() => getPackage(advisoryNo), [advisoryNo])
  const { state, retry, setData } = useLoad(advisoryNo > 0 ? loader : null)
  const { state: clausesState, retry: retryClauses } = useLoad(loadClauses)
  const clauses = useMemo(
    () => new Map(clausesState.status === 'ok' ? clausesState.data.map((c) => [c.id, c]) : []),
    [clausesState],
  )
  const [error, setError] = useState<(AdvisoryError & { itemId: number }) | null>(null)
  const [declareError, setDeclareError] = useState<AdvisoryError | null>(null)
  const [sitrepError, setSitrepError] = useState<AdvisoryError | null>(null)
  const [busy, setBusy] = useState(false)

  /** Sends one action with no second click; a failure goes to `onError` and a stale package reloads. */
  async function send(action: () => Promise<void>, onError: (error: ApiError) => void) {
    setBusy(true)
    try {
      await action()
    } catch (e) {
      const apiError = toApiError(e)
      onError(apiError)
      if (STALE_PACKAGE.has(apiError.code)) retry()
    } finally {
      setBusy(false)
    }
  }

  async function onDecide(item: PackageItem, action: DecisionAction, reason?: string) {
    setError(null)
    await send(
      async () => {
        setData(await postDecision(advisoryNo, item.id, { role, action, reason }))
      },
      (e) => setError({ advisoryNo, itemId: item.id, error: e }),
    )
  }

  async function onDeclare(level: ActivationLevel, reason?: string) {
    setDeclareError(null)
    await send(
      async () => {
        setData(await postDeclaration({ level, declared_by: role, reason }))
        onDeclared()
      },
      (e) => setDeclareError({ advisoryNo, error: e }),
    )
  }

  async function onApproveSitrep(text: string) {
    setSitrepError(null)
    await send(
      async () => {
        await approveSitrep(advisoryNo, role, text)
        retry()
      },
      (e) => setSitrepError({ advisoryNo, error: e }),
    )
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
          role={role}
          hoursToLandfall={hoursToLandfall}
          declareError={declareError?.advisoryNo === advisoryNo ? declareError.error : null}
          onDeclare={onDeclare}
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
