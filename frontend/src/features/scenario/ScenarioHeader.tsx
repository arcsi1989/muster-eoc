import type { ApiError } from '../../api/client'
import { LEVEL_LABEL } from '../../lib/labels'
import type { Scenario, TimelineSlot } from '../../types/scenario'

interface Props {
  scenario: Scenario
  busy: boolean
  actionError: ApiError | null
  onNext: () => void
  onReset: () => void
}

/** Consecutive slots with the same activation level, for the phase bands under the timeline. */
function phases(timeline: TimelineSlot[]) {
  const bands: { level: TimelineSlot['activation_level']; span: number }[] = []
  for (const slot of timeline) {
    const last = bands.at(-1)
    if (last && last.level === slot.activation_level) last.span += 1
    else bands.push({ level: slot.activation_level, span: 1 })
  }
  return bands
}

export function ScenarioHeader({ scenario, busy, actionError, onNext, onReset }: Props) {
  const atEnd = scenario.current_advisory >= scenario.total_advisories
  const columns = { gridTemplateColumns: `repeat(${scenario.timeline.length}, minmax(0, 1fr))` }

  return (
    <div className="scenario-header">
      <div className="timeline" aria-label="Advisory timeline">
        <ol className="timeline-slots" style={columns}>
          {scenario.timeline.map((slot) => {
            const state =
              slot.advisory_no === scenario.current_advisory ? 'current' : slot.issued ? 'past' : 'future'
            return (
              <li
                key={slot.advisory_no}
                className={`slot slot-${state}`}
                aria-current={state === 'current' ? 'step' : undefined}
              >
                <span className="dot" aria-hidden />
                <span className="slot-label">T-{slot.hours_to_landfall} h</span>
                <span className="visually-hidden">
                  Advisory {slot.advisory_no}, {state === 'future' ? 'not yet issued' : state}
                </span>
              </li>
            )
          })}
        </ol>
        <div className="timeline-phases" style={columns} aria-hidden>
          {phases(scenario.timeline).map((band, i) => (
            <span key={i} className={`phase phase-${band.level ?? 'none'}`} style={{ gridColumn: `span ${band.span}` }}>
              {band.level ? LEVEL_LABEL[band.level] : ''}
            </span>
          ))}
        </div>
      </div>
      <div className="scenario-actions">
        <button type="button" onClick={onNext} disabled={busy || atEnd}>
          {atEnd ? 'Landfall reached: last advisory' : `Issue advisory ${scenario.current_advisory + 1} ▶`}
        </button>
        <button type="button" className="secondary" onClick={onReset} disabled={busy || scenario.current_advisory === 0}>
          Reset
        </button>
      </div>
      {actionError && (
        <p role="alert" className="error-text">
          {actionError.message}
        </p>
      )}
    </div>
  )
}
