import { useState } from 'react'
import type { ApiError } from '../../api/client'
import { roleLabel } from '../../lib/roles'
import type { FieldTask } from '../../types/scenario'

const STATUS_LABEL: Record<FieldTask['status'], string> = {
  open: 'To do',
  done: 'Done',
  blocked: 'Blocked',
}

const wallClock = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

interface Props {
  task: FieldTask
  onDone: (task: FieldTask) => void
  onBlocked: (task: FieldTask, note: string) => void
  error?: ApiError | null
  /** a report is being sent: no second click */
  busy?: boolean
}

export function FieldTaskCard({ task, onDone, onBlocked, error, busy = false }: Props) {
  const [noting, setNoting] = useState(false)
  const [note, setNote] = useState('')
  const where = task.entity_name ? `${task.entity_id} ${task.entity_name}` : task.entity_id
  const reportable = task.status !== 'done' && !busy
  const stopped = task.stop_work.length > 0

  function submitBlocked() {
    onBlocked(task, note.trim())
    setNoting(false)
    setNote('')
  }

  return (
    <li className={`finding field-task item-${task.status}`}>
      <div className="finding-head">
        <span className="chip">{task.rule_id}</span>
        <span className="small">{where}</span>
        {stopped && <span className="badge overdue">Stop work: {task.stop_work.join(', ')}</span>}
        <span className={`badge status-${task.status}`}>{STATUS_LABEL[task.status]}</span>
      </div>
      <p className="action-text">{task.action}</p>
      <p className="small">{task.why}</p>
      <div className="finding-meta">
        {task.approved_by ? `Approved by ${roleLabel(task.approved_by)}` : 'Approved'} at advisory {task.approved_in}
        {task.approved_at && `, ${wallClock.format(new Date(task.approved_at))}`}
        {task.note && ` · “${task.note}”`}
      </div>
      {error && (
        <p role="alert" className="error-text small">
          {error.message}
        </p>
      )}
      {reportable && !noting && (
        <div className="item-actions">
          <button type="button" disabled={stopped} onClick={() => onDone(task)}>
            Done
          </button>
          <button type="button" className="secondary" onClick={() => setNoting(true)}>
            Blocked…
          </button>
        </div>
      )}
      {reportable && noting && (
        <div className="item-actions">
          <label className="reason">
            What blocks it
            <input value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
          </label>
          <button type="button" disabled={!note.trim()} onClick={submitBlocked}>
            Report blocked
          </button>
          <button type="button" className="secondary" onClick={() => setNoting(false)}>
            Cancel
          </button>
        </div>
      )}
    </li>
  )
}
