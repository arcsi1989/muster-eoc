import { useCallback, useState } from 'react'
import type { ApiError } from '../../api/client'
import { getDistricts, getFieldTasks, postFieldReport } from '../../api/scenario'
import { toApiError, useLatestData, useLoad } from '../../lib/useLoad'
import type { FieldTask } from '../../types/scenario'
import { FieldTaskCard } from './FieldTaskCard'

const loadDistricts = () => getDistricts()

/** Refusals that mean the list on screen is stale: reload it. */
const STALE_TASKS = new Set(['stop_work', 'already_done', 'package_closed', 'not_found'])

/** The field supervisor's view (CR-02 C2): one district's approved field tasks, marked done or
 * blocked. Read-only apart from the task status. */
export function FieldPage() {
  const districts = useLoad(loadDistricts)
  const [chosen, setChosen] = useState<string | null>(null)
  const district = chosen ?? (districts.state.status === 'ok' ? (districts.state.data[0] ?? null) : null)

  const loader = useCallback(() => getFieldTasks(district ?? ''), [district])
  const tasks = useLoad(district ? loader : null)
  const shown = useLatestData(tasks.state)
  const [error, setError] = useState<{ itemId: number; error: ApiError } | null>(null)
  const [busy, setBusy] = useState(false)

  async function report(task: FieldTask, outcome: 'done' | 'blocked', note?: string) {
    if (!district) return
    setError(null)
    setBusy(true)
    try {
      tasks.setData(await postFieldReport(task.item_id, outcome, district, note))
    } catch (e) {
      const apiError = toApiError(e)
      setError({ itemId: task.item_id, error: apiError })
      if (STALE_TASKS.has(apiError.code)) tasks.retry()
    } finally {
      setBusy(false)
    }
  }

  function choose(next: string) {
    setChosen(next)
    setError(null)
  }

  return (
    <main className="page">
      <h2>Field tasks</h2>
      <p className="hint">
        Approved work that needs a field crew, in your district. Mark a task done when the work is finished, or
        blocked with what stops it: a blocked task shows as a gap in the next decision package.
      </p>
      {districts.state.status === 'loading' && <p className="hint">Loading the districts…</p>}
      {districts.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the districts: {districts.state.error.message}</p>
          <button type="button" onClick={districts.retry}>
            Retry
          </button>
        </div>
      )}
      {districts.state.status === 'ok' && districts.state.data.length === 0 && (
        <p className="hint">The asset data has no districts.</p>
      )}
      {districts.state.status === 'ok' && district && (
        <label className="role-selector">
          District{' '}
          <select value={district} onChange={(e) => choose(e.target.value)}>
            {districts.state.data.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      )}
      {tasks.state.status === 'loading' && !shown && <p className="hint">Loading the field tasks…</p>}
      {tasks.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the field tasks: {tasks.state.error.message}</p>
          <button type="button" onClick={tasks.retry}>
            Retry
          </button>
        </div>
      )}
      {tasks.state.status !== 'error' && shown && shown.length === 0 && (
        <p className="hint">No approved field tasks in {district} yet.</p>
      )}
      {tasks.state.status !== 'error' && shown && shown.length > 0 && (
        <ul className="field-tasks">
          {shown.map((t) => (
            <FieldTaskCard
              key={t.item_id}
              task={t}
              busy={busy}
              error={error?.itemId === t.item_id ? error.error : null}
              onDone={(task) => void report(task, 'done')}
              onBlocked={(task, note) => void report(task, 'blocked', note)}
            />
          ))}
        </ul>
      )}
    </main>
  )
}
