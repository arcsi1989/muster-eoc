import { useCallback, useMemo, useState } from 'react'
import { getRisk, getTerritory } from '../../api/scenario'
import { levelName } from '../../lib/labels'
import { useLatestData, useLoad } from '../../lib/useLoad'
import type { Advisory, Scenario } from '../../types/scenario'
import { ExplainDrawer } from '../explain/ExplainDrawer'
import { RiskList } from '../risk/RiskList'
import { RiskPanel } from '../risk/RiskPanel'
import { currentAdvisories } from '../scenario/currentAdvisory'
import { ScenarioHeader } from '../scenario/ScenarioHeader'
import { useScenario } from '../scenario/useScenario'
import { StormLegend } from './StormLegend'
import { StormMap } from './StormMap'
import { formatLocalTime, LOCAL_TIME_NAME, RISK_BAND_COLOR } from './stormTrack'

/** The default screen: the advisory's track and cone, SGW's assets by risk on top, the ranked list. */
export function StormMapScreen() {
  const scenario = useScenario()
  const territory = useLoad(getTerritory)
  const { currentNo, current, previous } = currentAdvisories(scenario.state.status === 'ok' ? scenario.state.data : null)

  const riskLoader = useCallback(() => getRisk(currentNo), [currentNo])
  const risk = useLoad(currentNo > 0 ? riskLoader : null)
  // The last ranked list stays on screen while the next advisory's loads, then reorders in place.
  const shownRisk = useLatestData(risk.state)
  const [selected, setSelected] = useState<string | null>(null)

  const assets = useMemo(() => (territory.state.status === 'ok' ? territory.state.data.assets : []), [territory.state])
  const assetsById = useMemo(() => new Map(assets.map((a) => [a.id, a])), [assets])
  const riskById = useMemo(() => new Map(shownRisk?.items.map((i) => [i.asset_id, i]) ?? []), [shownRisk])

  return (
    <div className="operations storm-screen">
      <header className="app-header">
        <div className="title">
          <h1>Muster</h1>
          <span className="hint">Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)</span>
        </div>
        {scenario.state.status === 'ok' && (
          <>
            <StormFacts scenario={scenario.state.data} advisory={current} />
            <ScenarioHeader
              scenario={scenario.state.data}
              busy={scenario.busy}
              actionError={scenario.actionError}
              onNext={scenario.next}
              onReset={scenario.reset}
            />
          </>
        )}
        {scenario.state.status === 'loading' && <p className="hint">Loading the scenario…</p>}
        {scenario.state.status === 'error' && (
          <div role="alert">
            <span className="error-text">Could not load the scenario: {scenario.state.error.message}</span>{' '}
            <button type="button" onClick={scenario.retry}>
              Retry
            </button>
          </div>
        )}
      </header>

      <main className="app-main">
        <section className="storm-pane" aria-label="Storm map">
          {territory.state.status === 'ok' && (
            <>
              <StormMap
                coastline={territory.state.data.coastline}
                districts={territory.state.data.districts}
                assets={assets}
                facilities={territory.state.data.facilities}
                stagingAreas={territory.state.data.stagingAreas}
                advisory={current}
                previous={previous}
                risk={riskById}
                onSelect={setSelected}
              />
              <p className="cone-note">Cone shows forecast track uncertainty, not the area that will be impacted.</p>
              <StormLegend />
            </>
          )}
          {territory.state.status === 'loading' && <p className="hint pad">Loading the map…</p>}
          {territory.state.status === 'error' && (
            <div role="alert" className="pad">
              <p className="error-text">Could not load the map: {territory.state.error.message}</p>
              <button type="button" onClick={territory.retry}>
                Retry
              </button>
            </div>
          )}
        </section>
        <aside className="side-pane">
          <section className="card" aria-label="Risk list">
            <h2>Risk list</h2>
            {shownRisk && risk.state.status !== 'error' ? (
              <RiskList
                items={shownRisk.items}
                assetsById={assetsById}
                onSelect={setSelected}
                swatchColor={(item) => RISK_BAND_COLOR[item.risk_band]}
              />
            ) : (
              <RiskPanel state={risk.state} assetsById={assetsById} onRetry={risk.retry} onSelect={setSelected} />
            )}
          </section>
        </aside>
        {selected && currentNo > 0 && (
          <ExplainDrawer assetId={selected} advisoryNo={currentNo} onClose={() => setSelected(null)} />
        )}
      </main>
    </div>
  )
}

function StormFacts({ scenario, advisory }: { scenario: Scenario; advisory: Advisory | undefined }) {
  if (!advisory) return <p className="storm-facts hint">No advisory issued yet.</p>
  const declared = scenario.timeline.find((s) => s.advisory_no === advisory.advisory_no)?.activation_level
  return (
    <dl className="storm-facts" aria-label="Current advisory">
      <div>
        <dt>Advisory</dt>
        <dd>{advisory.advisory_no}</dd>
      </div>
      <div>
        <dt>Issued</dt>
        <dd>
          {formatLocalTime(advisory.issued_at)} <span className="hint">{LOCAL_TIME_NAME}</span>
        </dd>
      </div>
      <div>
        <dt>To landfall</dt>
        <dd>{advisory.hours_to_landfall} h</dd>
      </div>
      <div>
        <dt>Declared</dt>
        <dd>{declared ? levelName(declared) : 'none yet'}</dd>
      </div>
    </dl>
  )
}
