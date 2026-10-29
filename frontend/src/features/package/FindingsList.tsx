import type { Clause, Finding } from '../../types/scenario'

const ROLE_LABEL: Record<string, string> = {
  planning: 'Planning',
  operations: 'Operations',
  logistics: 'Logistics',
  regulatory_liaison: 'Regulatory Liaison',
  incident_commander: 'Incident Commander',
}

function entityLabel(f: Finding): string {
  if (f.entity_kind === 'event') return 'EOC-wide'
  return f.entity_name ? `${f.entity_id} ${f.entity_name}` : f.entity_id
}

function detailText(f: Finding): string | null {
  const facilities = f.details['asset.feeds_facility_ids']
  if (Array.isArray(facilities) && facilities.length > 0) return `Feeds ${facilities.join(', ')}`
  const fuelled = f.details['event.generators_fuelled']
  const needed = f.details['event.critical_feeding_assets_top25']
  if (typeof fuelled === 'number' && typeof needed === 'number') {
    return `${fuelled} generators fuelled, ${needed} critical-feeding assets in the top 25`
  }
  const elapsed = f.details['event.hours_since_full_activation']
  const deadline = f.details['deadline_within_hours']
  if (typeof elapsed === 'number' && typeof deadline === 'number') {
    return `${elapsed} h since full activation (deadline ${deadline} h)`
  }
  return null
}

function ClauseChips({ ids, clauses }: { ids: string[]; clauses: Map<string, Clause> }) {
  return (
    <span className="chips">
      {ids.map((id) => (
        <span key={id} className="chip" title={clauses.get(id)?.title}>
          {id}
        </span>
      ))}
    </span>
  )
}

function FindingItem({ finding, clauses }: { finding: Finding; clauses: Map<string, Clause> }) {
  const detail = detailText(finding)
  return (
    <li className={`finding severity-${finding.severity}`}>
      <div className="finding-head">
        <ClauseChips ids={finding.cites} clauses={clauses} />
        <strong>{finding.title}</strong>
        {finding.overdue && <span className="badge overdue">Overdue</span>}
      </div>
      <div className="finding-meta">
        {entityLabel(finding)} · {ROLE_LABEL[finding.owner_role] ?? finding.owner_role}
        {detail && ` · ${detail}`}
      </div>
    </li>
  )
}

interface Props {
  findings: Finding[]
  clauses: Map<string, Clause>
}

/** Read-only playbook findings, grouped: conflicts first, then gaps, satisfied collapsed. */
export function FindingsList({ findings, clauses }: Props) {
  const conflicts = findings.filter((f) => f.status === 'conflict')
  const gaps = findings.filter((f) => f.status === 'open')
  const satisfied = findings.filter((f) => f.status === 'satisfied')

  if (findings.length === 0) return <p className="hint">No playbook rule applies at this advisory.</p>

  return (
    <div className="findings">
      {conflicts.length > 0 && (
        <section aria-label="Conflicts">
          <h3>Conflicts (Incident Commander decides) · {conflicts.length}</h3>
          <p className="hint small">Stop-work (P-4.7) blocks field work the playbook also requires. Safety prevails (P-8.2).</p>
          <ul>
            {conflicts.map((f) => (
              <FindingItem key={`${f.rule_id}-${f.entity_id}`} finding={f} clauses={clauses} />
            ))}
          </ul>
        </section>
      )}
      <section aria-label="Gaps">
        <h3>Gaps · {gaps.length}</h3>
        {gaps.length === 0 ? (
          <p className="hint">No open gaps.</p>
        ) : (
          <ul>
            {gaps.map((f) => (
              <FindingItem key={`${f.rule_id}-${f.entity_id}`} finding={f} clauses={clauses} />
            ))}
          </ul>
        )}
      </section>
      {satisfied.length > 0 && (
        <details>
          <summary>Satisfied · {satisfied.length}</summary>
          <ul>
            {satisfied.map((f) => (
              <FindingItem key={`${f.rule_id}-${f.entity_id}`} finding={f} clauses={clauses} />
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
