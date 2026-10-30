import type { ReactNode } from 'react'
import { formatCost, formatDuration, formatTokens } from '../../lib/format'
import type { RunTrace, TraceSpan, TraceTotals } from '../../types/scenario'
import { layoutWaterfall } from './waterfall'

const highlighted = (span: TraceSpan) => span.retries > 0 || span.fallback || span.status === 'error'

function modelLabel(span: TraceSpan): string {
  if (span.model) return span.model
  return span.provider ?? '—'
}

/** An advisory's spans as a waterfall of duration bars, with totals for the advisory and the run. */
export function RunTraceView({ trace }: { trace: RunTrace }) {
  const { rows, breaks } = layoutWaterfall(trace.spans)

  return (
    <>
      <TotalsTable advisoryNo={trace.advisory_no} advisory={trace.advisory_totals} run={trace.run_totals} />
      {rows.length === 0 ? (
        <p className="hint">No spans recorded for advisory {trace.advisory_no} in this demo run.</p>
      ) : (
        <section className="card" aria-label="Spans">
          <table className="trace-waterfall" aria-label={`Waterfall of advisory ${trace.advisory_no}`}>
            <thead>
              <tr>
                <th scope="col">Step</th>
                <th scope="col" className="trace-axis">
                  Time
                  {breaks.map((b) => (
                    <span
                      key={b.at}
                      className="trace-break"
                      style={{ left: `${b.at}%` }}
                      title={`${formatDuration(b.idleMs)} idle, shortened`}
                    >
                      ⋯ {formatDuration(b.idleMs)} idle
                    </span>
                  ))}
                </th>
                <th scope="col">Duration</th>
                <th scope="col">Model</th>
                <th scope="col">Tokens</th>
                <th scope="col">Est. cost</th>
                <th scope="col">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ span, depth, left, width }) => (
                <tr key={span.span_id} className={highlighted(span) ? 'trace-highlight' : undefined}>
                  <td className={`trace-depth-${depth}`}>{span.node}</td>
                  <td className="trace-track">
                    <span
                      role="img"
                      aria-label={`${span.node}: ${formatDuration(span.duration_ms)}`}
                      className={`trace-bar trace-bar-${span.kind} trace-bar-${span.status}${highlighted(span) ? ' trace-bar-highlight' : ''}`}
                      style={{ left: `${left}%`, width: `${width}%` }}
                    />
                  </td>
                  <td>{formatDuration(span.duration_ms)}</td>
                  <td>{modelLabel(span)}</td>
                  <td>{formatTokens(span.tokens_in, span.tokens_out)}</td>
                  <td>{span.cost_usd === null ? 'no price' : formatCost(span.cost_usd)}</td>
                  <td>
                    <SpanNotes span={span} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  )
}

function SpanNotes({ span }: { span: TraceSpan }) {
  return (
    <>
      {span.status === 'paused' && <span className="badge">Paused for decisions</span>}
      {span.status === 'error' && <span className="badge trace-badge-alert">Error</span>}
      {span.retries > 0 && (
        <span className="badge trace-badge-alert">
          {span.retries} {span.retries === 1 ? 'retry' : 'retries'}
        </span>
      )}
      {span.fallback && <span className="badge trace-badge-alert">Template fallback</span>}
      {span.fallback_reason && <span className="trace-reason">{span.fallback_reason}</span>}
      {span.attempts.length > 1 && (
        <details>
          <summary>{span.attempts.length} attempts</summary>
          <ol>
            {span.attempts.map((attempt, i) => (
              <li key={i}>{attemptLabel(attempt)}</li>
            ))}
          </ol>
        </details>
      )}
    </>
  )
}

/** One model attempt from the generation's attempt log: its model and what went wrong, if anything. */
function attemptLabel(attempt: Record<string, unknown>): string {
  const model = typeof attempt.model === 'string' ? attempt.model : 'unknown model'
  if (typeof attempt.error === 'string') return `${model}: ${attempt.error}`
  const problems = Array.isArray(attempt.problems) ? attempt.problems.map(String) : []
  return problems.length > 0 ? `${model}: rejected (${problems.join('; ')})` : `${model}: accepted`
}

function TotalsTable({ advisoryNo, advisory, run }: { advisoryNo: number; advisory: TraceTotals; run: TraceTotals }) {
  const lines: { label: string; value: (t: TraceTotals) => ReactNode }[] = [
    { label: 'Latency', value: (t) => formatDuration(t.latency_ms) },
    { label: 'Tokens', value: (t) => formatTokens(t.tokens_in, t.tokens_out) },
    {
      label: 'Estimated cost',
      value: (t) => (
        <>
          {formatCost(t.cost_usd)}
          {t.unpriced_spans > 0 && (
            <span className="hint">
              {' '}
              ({t.unpriced_spans} {t.unpriced_spans === 1 ? 'span' : 'spans'} with tokens but no price)
            </span>
          )}
        </>
      ),
    },
    { label: 'Retries', value: (t) => t.retries },
    { label: 'Template fallbacks', value: (t) => t.fallbacks },
  ]
  return (
    <section className="card" aria-label="Totals">
      <table className="trace-totals" aria-label="Totals">
        <thead>
          <tr>
            <td />
            <th scope="col">Advisory {advisoryNo}</th>
            <th scope="col">Demo run</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.label}>
              <th scope="row">{line.label}</th>
              <td>{line.value(advisory)}</td>
              <td>{line.value(run)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">Prices from config/llm.yaml; the template costs nothing.</p>
    </section>
  )
}
