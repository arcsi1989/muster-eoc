import { useCallback, useState } from 'react'
import type { ApiError } from '../../api/client'
import { getDisagreements } from '../../api/scenario'
import { captureLabel, formatPercent } from '../../lib/format'
import { roleLabel } from '../../lib/roles'
import { useLoad } from '../../lib/useLoad'
import type { Challenger, ModelMetrics, PromotionCriterion, Role } from '../../types/scenario'
import { ReliabilityChart } from '../calibration/ReliabilityChart'
import { RoleSelector } from '../package/RoleSelector'
import { currentAdvisories } from '../scenario/currentAdvisory'
import { useScenario } from '../scenario/useScenario'
import { ChallengerFeatures } from './ChallengerFeatures'
import { useChallenger } from './useChallenger'

const auc = (m: ModelMetrics) => (m.roc_auc === null ? 'n/a' : m.roc_auc.toFixed(3))

const CRITERION: Record<PromotionCriterion['name'], { label: string; format: (v: number) => string; bound: string }> = {
  brier_improvement: { label: 'Brier score lower by', format: (v) => v.toFixed(3), bound: 'at least' },
  top_capture_gain: {
    label: 'Top-decile capture higher by',
    format: (v) => `${(v * 100).toFixed(1)} pts`,
    bound: 'at least',
  },
  calibration_error: { label: 'Calibration error', format: (v) => v.toFixed(3), bound: 'at most' },
}

/** Both risk models on the held-out storm, the promotion rule, and where they disagree now. */
export function ChallengerPage() {
  const { challenger, busy, actionError, propose, approve } = useChallenger()

  return (
    <main className="page">
      <h2>Champion and challenger</h2>
      <p className="hint">
        The rule-based score is the champion: it ranks every advisory. The challenger, a model trained on 20 synthetic
        past storms, scores every advisory in shadow and drives nothing. Both are compared on Storm Delta, a storm the
        challenger never saw. The synthetic history holds only the effects it was built with, so the challenger's
        accuracy says nothing about SGW's own assets.
      </p>
      {challenger.state.status === 'loading' && <p className="hint">Loading the challenger…</p>}
      {challenger.state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the challenger: {challenger.state.error.message}</p>
          <button type="button" onClick={challenger.retry}>
            Retry
          </button>
        </div>
      )}
      {challenger.state.status === 'ok' && challenger.state.data === null && (
        <p className="hint">No challenger model is loaded: run make train, then restart the backend.</p>
      )}
      {challenger.state.status === 'ok' && challenger.state.data && (
        <>
          <HeldOut challenger={challenger.state.data} />
          <Promotion
            challenger={challenger.state.data}
            busy={busy}
            actionError={actionError}
            onPropose={propose}
            onApprove={approve}
          />
          <DisagreementsSection />
        </>
      )}
    </main>
  )
}

function HeldOut({ challenger: c }: { challenger: Challenger }) {
  const championLabel = 'Champion: published curves'
  const challengerLabel = `Challenger: version ${c.model_version.id}`
  return (
    <section className="card calibration-result" aria-label="Held-out comparison">
      <h3>
        Held-out storm {c.promotion.storm}: {c.champion.assets} assets, {c.champion.failures} failed
      </h3>
      <div className="calibration-grid">
        <ReliabilityChart
          first={{ label: championLabel, reliability: c.champion.reliability }}
          second={{ label: challengerLabel, reliability: c.challenger.reliability }}
        />
        <div>
          <table className="lineage" aria-label="Metrics on the held-out storm">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col" className="num">
                  Champion
                </th>
                <th scope="col" className="num">
                  Challenger
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Brier score (lower is better)</th>
                <td className="num">{c.champion.brier.toFixed(3)}</td>
                <td className="num">{c.challenger.brier.toFixed(3)}</td>
              </tr>
              <tr>
                <th scope="row">ROC AUC (higher is better)</th>
                <td className="num">{auc(c.champion)}</td>
                <td className="num">{auc(c.challenger)}</td>
              </tr>
              <tr>
                <th scope="row">{captureLabel(c.challenger.top_fraction)} (higher is better)</th>
                <td className="num">{formatPercent(c.champion.top_capture)}</td>
                <td className="num">{formatPercent(c.challenger.top_capture)}</td>
              </tr>
            </tbody>
          </table>
          <p className="hint small">
            {captureLabel(c.challenger.top_fraction)}: the share of all failures among the{' '}
            {formatPercent(c.challenger.top_fraction)} of assets with the highest predicted probability.
          </p>
        </div>
      </div>
    </section>
  )
}

interface PromotionProps {
  challenger: Challenger
  busy: boolean
  actionError: ApiError | null
  onPropose: () => void
  onApprove: (role: Role) => void
}

function Promotion({ challenger: c, busy, actionError, onPropose, onApprove }: PromotionProps) {
  const [role, setRole] = useState<Role>('planning')
  const version = c.model_version
  const failed = c.promotion.criteria.filter((x) => !x.passed)

  return (
    <section className="card" aria-label="Promotion">
      <h3>Promotion rule</h3>
      <table className="lineage" aria-label="Promotion criteria">
        <thead>
          <tr>
            <th scope="col">Criterion on {c.promotion.storm}</th>
            <th scope="col" className="num">
              Challenger
            </th>
            <th scope="col" className="num">
              Required
            </th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {c.promotion.criteria.map((x) => {
            const { label, format, bound } = CRITERION[x.name]
            return (
              <tr key={x.name}>
                <th scope="row">{label}</th>
                <td className="num">{format(x.value)}</td>
                <td className="num">
                  {bound} {format(x.threshold)}
                </td>
                <td>{x.passed ? 'passed' : 'failed'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {version.status === 'approved' && version.in_use && (
        <p>
          <span className="badge status-approved">Champion</span> The challenger was promoted
          {version.approved_by && ` by ${roleLabel(version.approved_by)}`}: it ranks every advisory from the next one.
        </p>
      )}
      {version.status === 'approved' && !version.in_use && (
        <p className="hint">A later approval replaced the challenger as champion; it cannot be proposed again.</p>
      )}
      {version.status === 'shadow' && !c.promotion.passed && (
        <p className="hint">
          The rule does not allow a proposal: {failed.map((x) => CRITERION[x.name].label.toLowerCase()).join(', ')}{' '}
          failed. The rules stay champion.
        </p>
      )}
      {version.status === 'shadow' && c.promotion.passed && (
        <>
          <p>
            The challenger passes the rule, so it may be proposed. Proposing changes nothing: the rules stay champion
            until a person approves the promotion.
          </p>
          <button type="button" onClick={onPropose} disabled={busy}>
            Propose the challenger for promotion
          </button>
        </>
      )}
      {version.status === 'proposed' && (
        <>
          <p>
            Model version {version.id} is <strong>proposed</strong>: approving it makes the challenger the champion,
            and it ranks the next advisory.
          </p>
          <div className="calibration-actions">
            <RoleSelector role={role} onChange={setRole} />
            <button type="button" onClick={() => onApprove(role)} disabled={busy}>
              Approve the promotion
            </button>
          </div>
        </>
      )}
      {actionError && (
        <p role="alert" className="error-text">
          Not done: {actionError.message}
        </p>
      )}
    </section>
  )
}

function DisagreementsSection() {
  const scenario = useScenario()
  const { currentNo } = currentAdvisories(scenario.state.status === 'ok' ? scenario.state.data : null)
  const loader = useCallback(() => getDisagreements(currentNo), [currentNo])
  const { state, retry } = useLoad(currentNo > 0 ? loader : null)

  return (
    <section className="card" aria-label="Disagreements">
      <h3>Disagreements{currentNo > 0 && ` at advisory ${currentNo}`}</h3>
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
        <p className="hint">No advisory issued yet: the models are compared on each advisory once it is issued.</p>
      )}
      {state.status === 'loading' && <p className="hint">Loading the disagreements…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the disagreements: {state.error.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && state.data.items.length === 0 && (
        <p className="hint">
          No disagreements: the challenger ranks no asset in its top {state.data.top_n} that the champion leaves out
          (or, as the champion, it did not run in shadow).
        </p>
      )}
      {state.status === 'ok' && state.data.items.length > 0 && (
        <>
          <p className="hint small">
            Assets the challenger ranks in its top {state.data.top_n} that the champion does not, and the challenger's
            top features: why it ranks them higher. The champion's ranking is the one the playbook and the package use.
          </p>
          <table className="lineage" aria-label="Disagreements list">
            <thead>
              <tr>
                <th scope="col">Asset</th>
                <th scope="col" className="num">
                  Challenger
                </th>
                <th scope="col" className="num">
                  Champion
                </th>
                <th scope="col">Why (challenger's top features)</th>
              </tr>
            </thead>
            <tbody>
              {state.data.items.map((d) => (
                <tr key={d.asset_id}>
                  <th scope="row">
                    {d.asset_id} {d.asset_name}
                  </th>
                  <td className="num">
                    rank {d.challenger_rank} · {formatPercent(d.challenger_p_fail)}
                  </td>
                  <td className="num">
                    rank {d.champion_rank} · {formatPercent(d.champion_p_fail)}
                  </td>
                  <td>
                    <ChallengerFeatures features={d.top_features} label={`Why the challenger ranks ${d.asset_id}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
