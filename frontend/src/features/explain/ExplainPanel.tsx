import { formatCustomers, formatPercent } from '../../lib/format'
import type { Explanation } from '../../types/scenario'
import { ChallengerFeatures } from '../challenger/ChallengerFeatures'

function Bar({ label, value, max, text }: { label: string; value: number; max: number; text: string }) {
  const width = max > 0 ? Math.min(100, (100 * value) / max) : 0
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <span className="bar-track" aria-hidden>
        <span className="bar-fill" style={{ width: `${width}%` }} />
      </span>
      <span className="bar-value">{text}</span>
    </div>
  )
}

export function ExplainPanel({ explanation: e }: { explanation: Explanation }) {
  const c = e.consequence
  const downstream = c.downstream_assets.reduce((sum, a) => sum + a.customers, 0)
  const facilities = c.facilities.reduce((sum, f) => sum + f.weight, 0)
  const conditionCut = 1 - e.wind.theta_adjusted / e.wind.theta

  return (
    <div className="explain">
      <p className="headline">
        Rank {e.rank} · risk {formatCustomers(e.risk)}
        <span className={`badge confidence-badge-${e.confidence}`}>{e.confidence} confidence</span>
      </p>
      {e.confidence_reasons.length > 0 && (
        <ul className="hint small">
          {e.confidence_reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      <h3>Failure probability {formatPercent(e.p_fail)}</h3>
      <Bar label="Wind" value={e.p_wind} max={1} text={formatPercent(e.p_wind)} />
      <Bar label="Flood" value={e.p_flood} max={1} text={formatPercent(e.p_flood)} />
      <p className="hint small">
        Each of the 50 forecast variants combines both hazards (either can fail the asset); the failure probability is
        the average over the variants, so it is not simply the two bars combined.
      </p>
      <p className="hint small">
        Wind {e.exposure.wind_p50_mph}/{e.exposure.wind_p90_mph} mph against a median capacity of{' '}
        {e.wind.theta_adjusted.toFixed(0)} mph; flood {e.exposure.flood_depth_p50_m}/{e.exposure.flood_depth_p90_m} m
        against {e.flood.theta_adjusted.toFixed(2)} m (P50/P90).
        {conditionCut > 0 &&
          ` Condition ${e.asset.condition_score}/5 lowers its capacity by ${formatPercent(conditionCut)}.`}
      </p>

      {e.challenger && (
        <section className="challenger-beside" aria-label="Challenger in shadow">
          <h3>
            Challenger: rank {e.challenger.rank} · {formatPercent(e.challenger.p_fail)}
          </h3>
          <ChallengerFeatures features={e.challenger.top_features} label="Challenger's top features" />
          <p className="hint small">
            In shadow (model version {e.challenger.model_version}): it ranks nothing until a person approves its
            promotion. Each feature's points are how much it raises the challenger's failure probability.
          </p>
        </section>
      )}

      <h3>Consequence {formatCustomers(c.total)} customer-equivalents</h3>
      <Bar label="Own customers" value={c.own_customers} max={c.total} text={formatCustomers(c.own_customers)} />
      <Bar label="Downstream" value={downstream} max={c.total} text={formatCustomers(downstream)} />
      <Bar label="Critical facilities" value={facilities} max={c.total} text={formatCustomers(facilities)} />

      <h3>Dependencies</h3>
      <p className="small">
        <strong>Feeds:</strong>{' '}
        {e.feeds.length ? e.feeds.map((d) => `${d.id} ${d.name}`).join(', ') : 'nothing'}
      </p>
      <p className="small">
        <strong>Fed by:</strong>{' '}
        {e.fed_by.length ? e.fed_by.map((d) => `${d.id} ${d.name}`).join(', ') : 'no upstream asset'}
      </p>
    </div>
  )
}
