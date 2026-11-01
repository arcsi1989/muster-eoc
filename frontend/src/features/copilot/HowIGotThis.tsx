import type { CopilotStep, CopilotWork } from '../../types/scenario'
import { stepLabel, toolCallLabel } from './steps'

function cost(work: CopilotWork): string {
  if (work.cost_usd === null) return 'no price for this model in config/llm.yaml'
  return work.cost_usd === 0 ? '$0 (no model tokens)' : `$${work.cost_usd.toFixed(4)} (estimate)`
}

/** Under each answer: what the copilot did to get it, collapsed until asked for. */
export function HowIGotThis({ work, steps }: { work: CopilotWork; steps: CopilotStep[] }) {
  return (
    <details className="how-i-got-this">
      <summary>How I got this</summary>
      <dl className="work-facts">
        <dt>Answered by</dt>
        <dd>
          {work.fallback ? 'The template (fallback)' : work.provider}
          {work.model && ` · ${work.model}`}
        </dd>
        <dt>Prompt version</dt>
        <dd>{work.prompt_version ?? 'none (the template uses no prompt)'}</dd>
        <dt>Validation</dt>
        <dd>
          {work.validated
            ? 'Passed: every ID and number came from a tool'
            : 'Not validated: the deterministic template answered instead'}
        </dd>
        <dt>Retries</dt>
        <dd>{work.retries}</dd>
        <dt>Tokens</dt>
        <dd>
          {work.input_tokens.toLocaleString('en-US')} in · {work.output_tokens.toLocaleString('en-US')} out
        </dd>
        <dt>Estimated cost</dt>
        <dd>{cost(work)}</dd>
        {work.fallback_reason && (
          <>
            <dt>Why the template answered</dt>
            <dd>{work.fallback_reason}</dd>
          </>
        )}
      </dl>
      <h4>Attempts</h4>
      <ol className="work-list">
        {work.attempts.map((a, i) => (
          <li key={i}>
            {a.provider}
            {a.model && ` · ${a.model}`} · {a.latency_ms} ms
            {a.error
              ? ` · failed: ${a.error}`
              : a.problems.length
                ? ` · rejected: ${a.problems.join('; ')}`
                : ' · validated'}
          </li>
        ))}
      </ol>
      <h4>Tools, as the model saw them</h4>
      {work.tool_calls.length === 0 && <p className="hint small">No tool was called.</p>}
      <ol className="work-list">
        {work.tool_calls.map((call, i) => (
          <li key={i}>
            <details>
              <summary>
                <code>{toolCallLabel(call.name, call.args)}</code>
              </summary>
              <pre className="tool-result">{JSON.stringify(call.result, null, 1)}</pre>
            </details>
          </li>
        ))}
      </ol>
      {steps.length > 0 && (
        <>
          <h4>Steps</h4>
          <ol className="work-list">
            {steps.map((s, i) => (
              <li key={i}>{stepLabel(s)}</li>
            ))}
          </ol>
        </>
      )}
    </details>
  )
}
