import { useCallback, useMemo } from 'react'
import { getAssets, getChanges, getCoastline, getRisk } from './api/scenario'
import { DisclaimerFooter } from './components/DisclaimerFooter'
import { TerritoryMap } from './features/map/TerritoryMap'
import { RiskPanel } from './features/risk/RiskPanel'
import { AdvisoryCard } from './features/scenario/AdvisoryCard'
import { ChangesPanel } from './features/scenario/ChangesPanel'
import { IntroPanel } from './features/scenario/IntroPanel'
import { ScenarioHeader } from './features/scenario/ScenarioHeader'
import { useScenario } from './features/scenario/useScenario'
import { useLoad } from './lib/useLoad'

const loadTerritory = () => Promise.all([getAssets(), getCoastline()])

export default function App() {
  const scenario = useScenario()
  const territory = useLoad(loadTerritory)

  const issued = scenario.state.status === 'ok' ? scenario.state.data.advisories : []
  const current = issued.at(-1)
  const previous = issued.at(-2)
  const currentNo = current?.advisory_no ?? 0

  const riskLoader = useCallback(() => getRisk(currentNo), [currentNo])
  const changesLoader = useCallback(() => getChanges(currentNo), [currentNo])
  const risk = useLoad(currentNo > 0 ? riskLoader : null)
  const changes = useLoad(currentNo > 0 ? changesLoader : null)

  const assets = useMemo(() => (territory.state.status === 'ok' ? territory.state.data[0] : []), [territory.state])
  const assetsById = useMemo(() => new Map(assets.map((a) => [a.id, a])), [assets])
  const scores = useMemo(
    () => new Map(risk.state.status === 'ok' ? risk.state.data.items.map((i) => [i.asset_id, i.score]) : []),
    [risk.state],
  )

  return (
    <div className="app">
      <header className="app-header">
        <div className="title">
          <h1>SGW Storm Preparation</h1>
          <span className="hint">Fictional replay</span>
        </div>
        {scenario.state.status === 'ok' && (
          <ScenarioHeader
            scenario={scenario.state.data}
            busy={scenario.busy}
            actionError={scenario.actionError}
            onNext={scenario.next}
            onReset={scenario.reset}
          />
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
        <section className="map-pane" aria-label="Territory map">
          {territory.state.status === 'ok' && (
            <TerritoryMap
              coastline={territory.state.data[1]}
              assets={assets}
              scores={scores}
              advisory={current}
              previous={previous}
            />
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
          {scenario.state.status === 'ok' && !current && <IntroPanel total={scenario.state.data.total_advisories} />}
          {current && (
            <>
              <AdvisoryCard advisory={current} previous={previous} />
              <ChangesPanel state={changes.state} assetsById={assetsById} onRetry={changes.retry} />
            </>
          )}
          <section className="card" aria-label="Risk list">
            <h2>Risk list</h2>
            <RiskPanel state={risk.state} assetsById={assetsById} onRetry={risk.retry} />
          </section>
        </aside>
      </main>

      <DisclaimerFooter />
    </div>
  )
}
