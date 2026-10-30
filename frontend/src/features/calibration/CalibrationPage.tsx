import { useState } from 'react'
import { captureLabel, formatPercent } from '../../lib/format'
import { roleLabel } from '../../lib/roles'
import type { Calibration, ModelVersion, Role } from '../../types/scenario'
import { RoleSelector } from '../package/RoleSelector'
import { ReliabilityChart } from './ReliabilityChart'
import { useCalibration } from './useCalibration'

const versionName = (v: ModelVersion) => `version ${v.id} (${v.label})`
const approvedBy = (v: ModelVersion) => (v.approved_by ? `, approved by ${roleLabel(v.approved_by)}` : '')

export function CalibrationPage() {
  const { versions, result, run, approve, approving, approveError } = useCalibration()
  const [role, setRole] = useState<Role>('planning')
  const inUse = versions.state.status === 'ok' ? versions.state.data.find((v) => v.in_use) : undefined

  return (
    <main className="page">
      <h2>Calibration</h2>
      <p className="hint">
        Back-tests the fragility curves on a past storm (Storm Delta) and fits them to its observed failures. The fit
        is a proposed model version: it scores nothing until a person approves it, and then scores the next advisory.
      </p>
      {versions.state.status === 'loading' && <p className="hint">Loading the model versions…</p>}
      {versions.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the model versions: {versions.state.error.message}</p>
          <button type="button" onClick={versions.retry}>
            Retry
          </button>
        </div>
      )}
      {inUse && (
        <p>
          Scoring uses {versionName(inUse)}
          {approvedBy(inUse)}.
        </p>
      )}

      <div className="calibration-actions">
        <RoleSelector role={role} onChange={setRole} />
        <button type="button" onClick={run} disabled={result.state.status === 'loading'}>
          Run the back-test
        </button>
      </div>

      {result.state.status === 'idle' && <p className="hint">No back-test run yet.</p>}
      {result.state.status === 'loading' && <p className="hint">Running the back-test…</p>}
      {result.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">The back-test failed: {result.state.error.message}</p>
          <button type="button" onClick={result.retry}>
            Retry
          </button>
        </div>
      )}
      {result.state.status === 'ok' && (
        <CalibrationResult
          calibration={result.state.data}
          approving={approving}
          approveError={approveError?.message ?? null}
          onApprove={(calibration) => approve(calibration, role)}
        />
      )}
    </main>
  )
}

interface ResultProps {
  calibration: Calibration
  approving: boolean
  approveError: string | null
  onApprove: (calibration: Calibration) => void
}

function CalibrationResult({ calibration, approving, approveError, onApprove }: ResultProps) {
  const { before, after, model_version: proposed } = calibration
  return (
    <section className="card calibration-result" aria-label="Back-test result">
      <h3>
        Back-test on {calibration.storm}: {before.assets} assets, {before.failures} failed
      </h3>
      <div className="calibration-grid">
        <ReliabilityChart
          first={{ label: `Before: version ${before.model_version}`, reliability: before.reliability }}
          second={{ label: `After: version ${after.model_version}`, reliability: after.reliability }}
        />
        <div>
          <table className="lineage" aria-label="Scores before and after">
            <thead>
              <tr>
                <th scope="col">Score</th>
                <th scope="col" className="num">
                  Before (version {before.model_version})
                </th>
                <th scope="col" className="num">
                  After (version {after.model_version})
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Brier score (lower is better)</th>
                <td className="num">{before.brier.toFixed(3)}</td>
                <td className="num">{after.brier.toFixed(3)}</td>
              </tr>
              <tr>
                <th scope="row">{captureLabel(after.top_fraction)} (higher is better)</th>
                <td className="num">{formatPercent(before.top_capture)}</td>
                <td className="num">{formatPercent(after.top_capture)}</td>
              </tr>
            </tbody>
          </table>
          <p className="hint small">
            {captureLabel(after.top_fraction)}: the share of all failures among the {formatPercent(after.top_fraction)} of assets with
            the highest predicted probability.
          </p>
          {proposed.status === 'approved' ? (
            <p>
              <span className="badge status-approved">Approved</span>{' '}
              {proposed.approved_by && `Approved by ${roleLabel(proposed.approved_by)}. `}Model {versionName(proposed)}{' '}
              scores the next advisory.
            </p>
          ) : (
            <>
              <p>
                Model {versionName(proposed)} is <strong>proposed</strong>: approving it scores the next advisory with it.
              </p>
              <button type="button" onClick={() => onApprove(calibration)} disabled={approving}>
                Approve model version {proposed.id}
              </button>
              {approveError && (
                <p role="alert" className="error-text">
                  Not approved: {approveError}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  )
}
