import { useState } from 'react'
import type { ApiError } from '../../api/client'
import { formatIssuedAt, LEVEL_NUMBER, levelName } from '../../lib/labels'
import { roleLabel } from '../../lib/roles'
import type { ActivationLevel, PackageItem, Role } from '../../types/scenario'

interface Props {
  /** the P-2.5 item of the package; its owner role is the role that declares the proposed level */
  item: PackageItem
  proposed: ActivationLevel
  /** the last declared level */
  declared: ActivationLevel | null
  /** of the package's advisory; null while the scenario is loading */
  hoursToLandfall: number | null
  role: Role
  /** the package is open: a level can be declared */
  open: boolean
  busy: boolean
  error: ApiError | null
  onDeclare: (level: ActivationLevel, reason?: string) => void
}

/** The P-2.5 activation proposal. The engine proposes; only a person's declaration changes the level. */
export function ActivationProposalCard({ item, proposed, declared, hoursToLandfall, role, open, busy, error, onDeclare }: Props) {
  const [reason, setReason] = useState('')
  const number = LEVEL_NUMBER[proposed]
  const declarer = item.owner_role
  const isDeclared = item.status === 'approved'
  const when = hoursToLandfall === null ? '' : ` at T-${hoursToLandfall} h`

  return (
    <section className={`proposal-card severity-${item.severity}`} aria-label="Activation proposal">
      <h3>
        <span className="chip">{item.rule_id}</span> Activation proposal: {levelName(proposed)}
      </h3>
      <p className="small">
        {hoursToLandfall !== null && `The storm is ${hoursToLandfall} h to landfall: the playbook's time threshold for ${levelName(proposed)} is reached. `}
        Declared now: {declared ? levelName(declared) : 'none'}.
      </p>
      {isDeclared && (
        <p className="finding-meta">
          Declared by {roleLabel(item.decided_by ?? declarer)}
          {item.decided_at && ` on ${formatIssuedAt(item.decided_at)}`}
          {when}
          {item.reason && ` · “${item.reason}”`}
        </p>
      )}
      {!isDeclared && !open && <p className="hint small">The package is closed; the level was not declared.</p>}
      {!isDeclared && open && (
        <div className="item-actions">
          {role === declarer ? (
            <label className="reason">
              Reason (optional)
              <input value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          ) : (
            <p className="hint small">
              Only the {roleLabel(declarer)} declares Level {number} (P-2.5). Choose that role to declare.
            </p>
          )}
          <button
            type="button"
            className="declare"
            disabled={busy || role !== declarer}
            onClick={() => onDeclare(proposed, reason.trim() || undefined)}
          >
            Declare Level {number}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error-text small">
          {error.message}
        </p>
      )}
    </section>
  )
}
