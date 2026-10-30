import { useState } from 'react'
import { currentAdvisories } from '../scenario/currentAdvisory'
import { useScenario } from '../scenario/useScenario'
import { RunTraceView } from './RunTraceView'
import { useRunTrace } from './useRunTrace'

/** What the agent did per advisory: the cycle nodes and model calls as a waterfall, with tokens,
 * estimated cost, retries and template fallbacks, and totals for the advisory and the demo run. */
export function RunTracePage() {
  const scenario = useScenario()
  const { currentNo } = currentAdvisories(scenario.state.status === 'ok' ? scenario.state.data : null)
  const [picked, setPicked] = useState<number | null>(null)
  const advisoryNo = picked !== null && picked <= currentNo ? picked : currentNo

  return (
    <main className="page run-trace">
      <h2>Run trace</h2>
      <p className="hint">
        Observability only: what each step of the advisory cycle and each model call took, used and cost. Decisions
        and approvals are in the audit log.
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
        <p className="hint">No advisory issued yet: each advisory's trace appears once it is issued.</p>
      )}
      {currentNo > 0 && (
        <>
          <div className="trace-picker" role="group" aria-label="Advisory">
            {Array.from({ length: currentNo }, (_, i) => i + 1).map((no) => (
              <button key={no} type="button" aria-pressed={no === advisoryNo} onClick={() => setPicked(no)}>
                Advisory {no}
              </button>
            ))}
          </div>
          <AdvisoryTrace advisoryNo={advisoryNo} />
        </>
      )}
    </main>
  )
}

function AdvisoryTrace({ advisoryNo }: { advisoryNo: number }) {
  const { state, retry } = useRunTrace(advisoryNo)
  if (state.status === 'loading') return <p className="hint">Loading the run trace…</p>
  if (state.status === 'error')
    return (
      <div role="alert">
        <p className="error-text">Could not load the run trace: {state.error.message}</p>
        <button type="button" onClick={retry}>
          Retry
        </button>
      </div>
    )
  if (state.status !== 'ok') return null
  return (
    <>
      <button type="button" className="secondary" onClick={retry}>
        Refresh
      </button>
      <RunTraceView trace={state.data} />
    </>
  )
}
