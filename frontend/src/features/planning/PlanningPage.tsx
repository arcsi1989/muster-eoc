import type { ApiError } from '../../api/client'
import { formatIssuedAt } from '../../lib/labels'
import { roleLabel } from '../../lib/roles'
import type { Commander, Ics215Row, IapObjective, Planning } from '../../types/scenario'
import { currentAdvisories } from '../scenario/currentAdvisory'
import { useScenario } from '../scenario/useScenario'
import { usePlanning } from './usePlanning'

const PLANNING_CHIEF = 'Planning Section Chief'

function wordingLabel(planning: Planning): string {
  if (planning.fallback) return `Template wording (the AI wording was not used: ${planning.fallback_reason})`
  if (planning.provider === 'template') return 'Template wording (offline)'
  return `AI wording (${planning.model ?? planning.provider}); the objectives and their citations come from the findings`
}

/** The planning products of the period after the current advisory: the ICS-215 and the IAP
 * objectives, DRAFT until the Planning Section Chief approves and the commander releases them. */
export function PlanningPage() {
  const scenario = useScenario()
  const { currentNo } = currentAdvisories(scenario.state.status === 'ok' ? scenario.state.data : null)

  return (
    <main className="page planning">
      <h2>ICS-215 and IAP objectives</h2>
      <p className="hint no-print">
        Drafted from approved package items and open findings for the next operational period. Code writes the rows
        and objectives; a model may only reword the objectives. Nothing is released until the Planning Section Chief
        approves and the commander releases it.
      </p>
      {scenario.state.status === 'loading' && <p className="hint">Loading the scenario…</p>}
      {scenario.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the scenario: {scenario.state.error.message}</p>
          <button type="button" onClick={scenario.retry}>
            Retry
          </button>
        </div>
      )}
      {scenario.state.status === 'ok' && currentNo === 0 && (
        <p className="hint">No advisory issued yet: the planning products are drafted after an advisory.</p>
      )}
      {currentNo > 0 && <PlanningProducts key={currentNo} advisoryNo={currentNo} />}
    </main>
  )
}

function PlanningProducts({ advisoryNo }: { advisoryNo: number }) {
  const { planning, pkg, busy, actionError, draft, release } = usePlanning(advisoryNo)
  const open = pkg.state.status === 'ok' && pkg.state.data.status === 'open'
  const commander = pkg.state.status === 'ok' ? pkg.state.data.decides_as_commander : null

  return (
    <>
      {pkg.state.status === 'error' && (
        <div role="alert" className="no-print">
          <p className="error-text">Could not load the decision package: {pkg.state.error.message}</p>
          <button type="button" onClick={pkg.retry}>
            Retry
          </button>
        </div>
      )}
      {planning.state.status === 'loading' && <p className="hint">Loading the planning draft…</p>}
      {planning.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the planning draft: {planning.state.error.message}</p>
          <button type="button" onClick={planning.retry}>
            Retry
          </button>
        </div>
      )}
      {planning.state.status === 'ok' && planning.state.data === null && (
        <section className="card" aria-label="No planning draft">
          <p>No planning draft for advisory {advisoryNo} yet.</p>
          {open ? (
            <button type="button" className="no-print" onClick={draft} disabled={busy}>
              Draft the ICS-215 and IAP objectives
            </button>
          ) : (
            pkg.state.status === 'ok' && (
              <p className="hint">The decision package for advisory {advisoryNo} is closed; nothing more is drafted.</p>
            )
          )}
          <ActionError error={actionError} />
        </section>
      )}
      {planning.state.status === 'ok' && planning.state.data && (
        <PlanningDraft
          planning={planning.state.data}
          open={open}
          commander={commander}
          busy={busy}
          actionError={actionError}
          onRedraft={draft}
          onRelease={release}
        />
      )}
    </>
  )
}

function ActionError({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <p role="alert" className="error-text no-print">
      Not done: {error.message}
    </p>
  )
}

interface DraftProps {
  planning: Planning
  open: boolean
  /** the role that commands at the advisory; null while the package is loading */
  commander: Commander | null
  busy: boolean
  actionError: ApiError | null
  onRedraft: () => void
  onRelease: (role: 'planning' | Commander) => void
}

function PlanningDraft({ planning, open, commander, busy, actionError, onRedraft, onRelease }: DraftProps) {
  const released = planning.status === 'released'
  return (
    <article aria-label="Planning products">
      <h3 className="planning-title">
        Advisory {planning.advisory_no}: operational period{' '}
        {`T-${planning.period_start_hours} to T-${planning.period_end_hours}`}{' '}
        {released ? (
          <span className="badge status-approved">Released</span>
        ) : (
          <span className="badge draft-badge">DRAFT</span>
        )}
      </h3>
      <p className="hint small">Drafted {formatIssuedAt(planning.drafted_at)}.</p>
      {open && !planning.planning_approved_at && (
        <button type="button" className="no-print" onClick={onRedraft} disabled={busy}>
          Redraft from the current decisions
        </button>
      )}

      <ReleaseApprovals planning={planning} open={open} commander={commander} busy={busy} onRelease={onRelease} />
      <ActionError error={actionError} />

      <section aria-label="ICS-215" className="planning-section">
        <h3>ICS-215 operational planning worksheet</h3>
        {planning.ics215.length === 0 ? (
          <p className="hint">No approved field work for this period.</p>
        ) : (
          <Ics215Table rows={planning.ics215} />
        )}
      </section>

      <section aria-label="IAP objectives" className="planning-section">
        <h3>IAP incident objectives</h3>
        <p className="hint small">{wordingLabel(planning)}</p>
        {planning.objectives.length === 0 ? (
          <p className="hint">No incident objectives.</p>
        ) : (
          <Objectives objectives={planning.objectives} />
        )}
      </section>
    </article>
  )
}

interface ApprovalsProps {
  planning: Planning
  open: boolean
  commander: Commander | null
  busy: boolean
  onRelease: (role: 'planning' | Commander) => void
}

/** The two release approvals, in order: the Planning Section Chief, then the commander. */
function ReleaseApprovals({ planning, open, commander, busy, onRelease }: ApprovalsProps) {
  const commanderLabel = commander ? roleLabel(commander) : 'the commander'
  return (
    <section aria-label="Release approvals" className="planning-section">
      <h3>Release</h3>
      <ol className="release-steps">
        <li>
          {planning.planning_approved_at ? (
            <span>
              Approved by the {PLANNING_CHIEF}, {formatIssuedAt(planning.planning_approved_at)}
            </span>
          ) : (
            <>
              <span>{PLANNING_CHIEF} approves the draft. </span>
              {open && (
                <button type="button" className="no-print" onClick={() => onRelease('planning')} disabled={busy}>
                  Approve as {PLANNING_CHIEF}
                </button>
              )}
            </>
          )}
        </li>
        <li>
          {planning.released_at && planning.released_by ? (
            <span>
              Released by the {roleLabel(planning.released_by)}, {formatIssuedAt(planning.released_at)}
            </span>
          ) : (
            <>
              <span>The {commanderLabel} releases it. </span>
              {open && commander && (
                <button
                  type="button"
                  className="no-print"
                  onClick={() => onRelease(commander)}
                  disabled={busy || !planning.planning_approved_at}
                >
                  Release as {commanderLabel}
                </button>
              )}
              {open && !planning.planning_approved_at && (
                <span className="hint small no-print"> After the {PLANNING_CHIEF} approves.</span>
              )}
            </>
          )}
        </li>
      </ol>
      {!open && planning.status === 'DRAFT' && (
        <p className="hint">The decision package for advisory {planning.advisory_no} is closed; this draft was not released.</p>
      )}
    </section>
  )
}

function Ics215Table({ rows }: { rows: Ics215Row[] }) {
  return (
    <table className="lineage ics215" aria-label="ICS-215 work assignments">
      <thead>
        <tr>
          <th scope="col">Location</th>
          <th scope="col">Work assignment</th>
          <th scope="col">Resource kind</th>
          <th scope="col" className="num">
            Required
          </th>
          <th scope="col" className="num">
            Have
          </th>
          <th scope="col" className="num">
            Need
          </th>
          <th scope="col">Reporting location</th>
          <th scope="col">Requested arrival</th>
          <th scope="col">Clause</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.item_id}-${row.resource_kind}`} className={row.need > 0 ? 'has-issues' : undefined}>
            <td>
              {row.location} ({row.location_id})
              {row.stop_work.map((clause) => (
                <span key={clause} className="badge overdue stop-work">
                  Stop work: {clause}
                </span>
              ))}
            </td>
            <td>{row.work_assignment}</td>
            <td>{row.resource_kind}</td>
            <td className="num">{row.required}</td>
            <td className="num">{row.have}</td>
            <td className="num">{row.need}</td>
            <td>
              {row.reporting_location ? `${row.reporting_location} (${row.reporting_location_id})` : 'No usable staging area'}
            </td>
            <td>T-{row.requested_arrival_hours}</td>
            <td>
              <span className="chip">{row.clause_id}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Objectives({ objectives }: { objectives: IapObjective[] }) {
  return (
    <ol className="objectives">
      {objectives.map((objective, i) => (
        <li key={i}>
          {objective.text}{' '}
          <span className="chips" aria-label="Cited clauses">
            {objective.clause_ids.map((id) => (
              <span key={id} className="chip">
                {id}
              </span>
            ))}
          </span>
        </li>
      ))}
    </ol>
  )
}
