import { useCallback, useMemo } from 'react'
import { getClauses, getFindings } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'
import { FindingsList } from './FindingsList'

const loadClauses = () => getClauses()

export function PackagePanel({ advisoryNo }: { advisoryNo: number }) {
  const findingsLoader = useCallback(() => getFindings(advisoryNo), [advisoryNo])
  const findings = useLoad(advisoryNo > 0 ? findingsLoader : null)
  const { state: clausesState, retry: retryClauses } = useLoad(loadClauses)
  const clauses = useMemo(
    () => new Map(clausesState.status === 'ok' ? clausesState.data.map((c) => [c.id, c]) : []),
    [clausesState],
  )

  return (
    <section className="card" aria-label="Decision package">
      <h2>Playbook findings</h2>
      <p className="hint small">Evaluated by the rule engine against playbook EOP-HUR-01. Decisions come next.</p>
      {clausesState.status === 'error' && (
        <p role="alert" className="error-text small">
          Clause titles unavailable: {clausesState.error.message}{' '}
          <button type="button" className="link" onClick={retryClauses}>
            Retry
          </button>
        </p>
      )}
      {findings.state.status === 'idle' && <p className="hint">Issue advisory 1 to evaluate the playbook.</p>}
      {findings.state.status === 'loading' && <p className="hint">Evaluating the playbook…</p>}
      {findings.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the findings: {findings.state.error.message}</p>
          <button type="button" onClick={findings.retry}>
            Retry
          </button>
        </div>
      )}
      {findings.state.status === 'ok' && <FindingsList findings={findings.state.data} clauses={clauses} />}
    </section>
  )
}
