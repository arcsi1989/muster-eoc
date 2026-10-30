import { useCallback, useState } from 'react'
import { getAudit } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'
import type { AuditActor } from '../../types/scenario'
import { AuditList } from './AuditList'

type ActorFilter = AuditActor | 'all'

const FILTERS: { value: ActorFilter; label: string }[] = [
  { value: 'all', label: 'Everyone' },
  { value: 'system', label: 'System' },
  { value: 'agent', label: 'Agent (LLM)' },
  { value: 'human', label: 'People' },
  { value: 'field_supervisor', label: 'Field supervisors' },
]

export function AuditPage() {
  const [actor, setActor] = useState<ActorFilter>('all')
  const loader = useCallback(() => getAudit(actor === 'all' ? undefined : actor), [actor])
  const { state, retry } = useLoad(loader)

  return (
    <main className="page">
      <h2>Audit trail</h2>
      <p className="hint">
        Every step of the advisory cycle, every model call and every decision, newest first. Scenario time is the
        advisory in force; the clock time is when it happened.
      </p>
      <label className="role-selector">
        Show{' '}
        <select value={actor} onChange={(e) => setActor(e.target.value as ActorFilter)}>
          {FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </label>
      {state.status === 'loading' && <p className="hint">Loading the audit trail…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the audit trail: {state.error.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && <AuditList events={state.data} />}
    </main>
  )
}
