import { formatWallClock } from '../../lib/format'
import { roleLabel } from '../../lib/roles'
import type { AuditEvent } from '../../types/scenario'

function scenarioTime(e: AuditEvent): string {
  if (e.advisory_no === null) return 'Before advisory 1'
  return e.hours_to_landfall === null
    ? `Advisory ${e.advisory_no}`
    : `Advisory ${e.advisory_no} · T-${e.hours_to_landfall} h`
}

interface Attempt {
  provider?: string
  model?: string | null
  latency_ms?: number
  usage?: { input_tokens?: number; output_tokens?: number }
  error?: string
}

/** The facts a reader looks for first, by event type: who decided what, which model ran. */
function KeyFacts({ e }: { e: AuditEvent }) {
  const p = e.payload
  if (e.type === 'decision' || e.type === 'sitrep_approved') {
    return (
      <p className="small audit-facts">
        Role: {roleLabel(String(p.role ?? ''))}
        {typeof p.action === 'string' && ` · action: ${p.action}`}
        {typeof p.reason === 'string' && ` · reason: “${p.reason}”`}
        {typeof p.edited === 'boolean' && ` · ${p.edited ? 'edited' : 'as drafted'}`}
      </p>
    )
  }
  if (e.type === 'items_not_decided' && Array.isArray(p.items) && p.items.length > 0) {
    const items = p.items as { rule_id: string; entity_id: string }[]
    return <p className="small audit-facts">Not decided: {items.map((i) => `${i.rule_id} ${i.entity_id}`).join(', ')}</p>
  }
  if (Array.isArray(p.attempts) && p.attempts.length > 0) {
    return (
      <ul className="small audit-facts">
        {(p.attempts as Attempt[]).map((a, i) => (
          <li key={i}>
            Model call {i + 1}: {a.model ?? a.provider}
            {a.latency_ms !== undefined && ` · ${a.latency_ms} ms`}
            {a.usage && ` · ${a.usage.input_tokens ?? 0} in / ${a.usage.output_tokens ?? 0} out tokens`}
            {a.error && ` · ${a.error}`}
          </li>
        ))}
      </ul>
    )
  }
  return null
}

export function AuditList({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <p className="hint">No events yet. Issue an advisory to start the log.</p>
  return (
    <ol className="audit-list">
      {events.map((e) => (
        <li key={e.id} className={`audit-event actor-${e.actor}`}>
          <div className="audit-head">
            <span className={`badge actor-badge-${e.actor}`}>{e.actor}</span>
            <span className="small">{scenarioTime(e)}</span>
            <span className="hint small">{formatWallClock(e.recorded_at, { seconds: true })}</span>
            <code className="small">{e.type}</code>
          </div>
          <p className="audit-summary">{e.summary}</p>
          <KeyFacts e={e} />
          <details>
            <summary className="small">Details</summary>
            <dl className="audit-details small">
              <dt>Input hash</dt>
              <dd>
                <code>{e.input_hash}</code>
              </dd>
              <dt>Versions</dt>
              <dd>
                {Object.entries(e.versions)
                  .filter(([, v]) => v !== null && v !== undefined)
                  .map(([k, v]) => `${k}: ${String(v)}`)
                  .join(' · ') || '—'}
              </dd>
            </dl>
            <pre className="audit-payload">{JSON.stringify(e.payload, null, 2)}</pre>
          </details>
        </li>
      ))}
    </ol>
  )
}
