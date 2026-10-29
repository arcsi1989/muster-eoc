import { useState } from 'react'
import type { ApiError } from '../../api/client'
import { roleLabel } from '../../lib/roles'
import type { DecisionAction, PackageItem } from '../../types/scenario'

const STATUS_LABEL: Record<PackageItem['status'], string> = {
  pending: 'Pending',
  approved: 'Approved',
  overridden: 'Overridden',
  deferred: 'Deferred',
  alternative: 'Alternative measure',
  not_decided: 'Not decided',
}

interface Props {
  item: PackageItem
  open: boolean
  onDecide: (item: PackageItem, action: DecisionAction, reason?: string) => void
  error?: ApiError | null
  /** a decision is being sent: no second click */
  busy?: boolean
}

export function ItemCard({ item, open, onDecide, error, busy = false }: Props) {
  const [reasonFor, setReasonFor] = useState<DecisionAction | null>(null)
  const [reason, setReason] = useState('')
  const entity = item.entity_id === 'event' ? 'EOC-wide' : `${item.entity_id}${item.entity_name ? ` ${item.entity_name}` : ''}`
  const decidable = open && item.status === 'pending' && !busy

  function submit(action: DecisionAction) {
    onDecide(item, action, reason.trim() || undefined)
    setReasonFor(null)
    setReason('')
  }

  return (
    <li className={`finding severity-${item.severity} item-${item.status}`}>
      <div className="finding-head">
        <span className="chips">
          {item.cites.map((id) => (
            <span key={id} className="chip">
              {id}
            </span>
          ))}
        </span>
        <span className="small">{entity}</span>
        {item.overdue && <span className="badge overdue">Overdue</span>}
        <span className={`badge status-${item.status}`}>{STATUS_LABEL[item.status]}</span>
      </div>
      <p className="action-text">{item.proposed_action}</p>
      <div className="finding-meta">
        Owner: {roleLabel(item.owner_role)}
        {item.decided_by && ` · decided by ${roleLabel(item.decided_by)}`}
        {item.reason && ` · “${item.reason}”`}
      </div>
      {error && (
        <p role="alert" className="error-text small">
          {error.message}
        </p>
      )}
      {decidable && reasonFor === null && (
        <div className="item-actions">
          {item.kind === 'gap' ? (
            <>
              <button type="button" onClick={() => submit('approve')}>
                Approve
              </button>
              <button type="button" className="secondary" onClick={() => setReasonFor('override')}>
                Override…
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => setReasonFor('defer')}>
                Defer…
              </button>
              <button type="button" className="secondary" onClick={() => setReasonFor('alternative')}>
                Alternative measure…
              </button>
            </>
          )}
        </div>
      )}
      {decidable && reasonFor !== null && (
        <div className="item-actions">
          <label className="reason">
            {reasonFor === 'alternative' ? 'Alternative measure and reason' : 'Reason'}
            <input value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
          </label>
          <button type="button" disabled={!reason.trim()} onClick={() => submit(reasonFor)}>
            {reasonFor === 'override' ? 'Override' : reasonFor === 'defer' ? 'Defer' : 'Record measure'}
          </button>
          <button type="button" className="secondary" onClick={() => setReasonFor(null)}>
            Cancel
          </button>
        </div>
      )}
    </li>
  )
}
