import { useCallback, useMemo, useState } from 'react'
import { getAlerts, getChanges, getExposure, getRisk, getTerritory } from './api/scenario'
import { DisclaimerFooter } from './components/DisclaimerFooter'
import { AlertsPanel } from './features/alerts/AlertsPanel'
import { AuditPage } from './features/audit/AuditPage'
import { CalibrationPage } from './features/calibration/CalibrationPage'
import { ChallengerPage } from './features/challenger/ChallengerPage'
import { CopilotPanel } from './features/copilot/CopilotPanel'
import { DataQualityPage } from './features/data-quality/DataQualityPage'
import { ExplainDrawer } from './features/explain/ExplainDrawer'
import { FieldPage } from './features/field/FieldPage'
import { PackagePanel } from './features/package/PackagePanel'
import { RoleSelector } from './features/package/RoleSelector'
import { TerritoryMap } from './features/map/TerritoryMap'
import { PlanningPage } from './features/planning/PlanningPage'
import { RiskPanel } from './features/risk/RiskPanel'
import { AdvisoryCard } from './features/scenario/AdvisoryCard'
import { ChangesPanel } from './features/scenario/ChangesPanel'
import { currentAdvisories } from './features/scenario/currentAdvisory'
import { IntroPanel } from './features/scenario/IntroPanel'
import { ScenarioHeader } from './features/scenario/ScenarioHeader'
import { useScenario } from './features/scenario/useScenario'
import { StormMapScreen } from './features/storm-map/StormMapScreen'
import { RunTracePage } from './features/trace/RunTracePage'
import { PAGES, useHashRoute } from './lib/useHashRoute'
import { useLoad } from './lib/useLoad'
import type { Role } from './types/scenario'

export default function App() {
  const route = useHashRoute()
  return (
    <div className="app">
      <nav className="app-nav" aria-label="Pages">
        {PAGES.map((page) => (
          <a key={page.route} href={page.hash} aria-current={route === page.route ? 'page' : undefined}>
            {page.label}
          </a>
        ))}
      </nav>
      {route === 'storm-map' && <StormMapScreen />}
      {route === 'operations' && <OperationsScreen />}
      {route === 'field' && <FieldPage />}
      {route === 'planning' && <PlanningPage />}
      {route === 'audit' && <AuditPage />}
      {route === 'data-quality' && <DataQualityPage />}
      {route === 'calibration' && <CalibrationPage />}
      {route === 'challenger' && <ChallengerPage />}
      {route === 'trace' && <RunTracePage />}
      <DisclaimerFooter />
    </div>
  )
}

function OperationsScreen() {
  const scenario = useScenario()
  const territory = useLoad(getTerritory)

  const { currentNo, current, previous } = currentAdvisories(scenario.state.status === 'ok' ? scenario.state.data : null)

  const riskLoader = useCallback(() => getRisk(currentNo), [currentNo])
  const changesLoader = useCallback(() => getChanges(currentNo), [currentNo])
  const exposureLoader = useCallback(() => getExposure(currentNo), [currentNo])
  const exposure = useLoad(currentNo > 0 ? exposureLoader : null)
  const alertsLoader = useCallback(() => getAlerts(currentNo), [currentNo])
  const alerts = useLoad(currentNo > 0 ? alertsLoader : null)
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState<'risk' | 'package' | 'copilot'>('risk')
  const [role, setRole] = useState<Role>('director')
  const risk = useLoad(currentNo > 0 ? riskLoader : null)
  const changes = useLoad(currentNo > 0 ? changesLoader : null)

  const assets = useMemo(() => (territory.state.status === 'ok' ? territory.state.data.assets : []), [territory.state])
  const assetsById = useMemo(() => new Map(assets.map((a) => [a.id, a])), [assets])
  const pFail = useMemo(
    () => new Map(risk.state.status === 'ok' ? risk.state.data.items.map((i) => [i.asset_id, i.p_fail]) : []),
    [risk.state],
  )

  const exposureBySite = useMemo(
    () => new Map(exposure.state.status === 'ok' ? exposure.state.data.map((e) => [e.site_id, e]) : []),
    [exposure.state],
  )

  return (
    <div className="operations">
      <header className="app-header">
        <div className="title">
          <h1>Muster</h1>
          <span className="hint">Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)</span>
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
        <RoleSelector role={role} onChange={setRole} />
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
              coastline={territory.state.data.coastline}
              assets={assets}
              facilities={territory.state.data.facilities}
              stagingAreas={territory.state.data.stagingAreas}
              pFail={pFail}
              exposure={exposureBySite}
              advisory={current}
              previous={previous}
              onSelect={setSelected}
            />
          )}
          {exposure.state.status === 'error' && (
            <div role="alert" className="map-alert">
              <span className="error-text">Exposure unavailable: {exposure.state.error.message}</span>{' '}
              <button type="button" onClick={exposure.retry}>
                Retry
              </button>
            </div>
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
          <div className="tabs" role="tablist" aria-label="Side panel">
            <button type="button" role="tab" aria-selected={tab === 'risk'} onClick={() => setTab('risk')}>
              Risk list
            </button>
            <button type="button" role="tab" aria-selected={tab === 'package'} onClick={() => setTab('package')}>
              Decision package
            </button>
            <button type="button" role="tab" aria-selected={tab === 'copilot'} onClick={() => setTab('copilot')}>
              Copilot
            </button>
          </div>
          {tab === 'copilot' && <CopilotPanel onSelectAsset={setSelected} />}
          {tab === 'risk' && (
            <>
              {current && <AlertsPanel state={alerts.state} onRetry={alerts.retry} onSelect={setSelected} />}
              <section className="card" aria-label="Risk list">
                <h2>Risk list</h2>
                <RiskPanel state={risk.state} assetsById={assetsById} onRetry={risk.retry} onSelect={setSelected} />
              </section>
            </>
          )}
          {tab === 'package' && (
            <PackagePanel
              advisoryNo={currentNo}
              role={role}
              hoursToLandfall={current?.hours_to_landfall ?? null}
              assetsById={assetsById}
              onSelectAsset={setSelected}
              onDeclared={scenario.refresh}
            />
          )}
        </aside>
        {selected && currentNo > 0 && (
          <ExplainDrawer assetId={selected} advisoryNo={currentNo} onClose={() => setSelected(null)} />
        )}
      </main>
    </div>
  )
}
