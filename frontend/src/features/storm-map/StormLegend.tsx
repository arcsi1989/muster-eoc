import {
  CATEGORIES,
  CATEGORY_COLOR,
  CATEGORY_LABEL,
  LOCAL_TIME_NAME,
  RISK_BAND_COLOR,
  RISK_BAND_LABEL,
  RISK_BANDS,
} from './stormTrack'

const HURRICANE = CATEGORIES.filter((c) => c.startsWith('cat_'))

export function StormLegend() {
  return (
    <div className="storm-legend" aria-label="Map legend">
      <p>
        <strong>Hurricane: Cat 1 to Cat 5, tropical storm</strong>
      </p>
      <p className="legend-row">
        {[...HURRICANE, 'tropical_storm' as const].map((c) => (
          <span key={c} className="legend-item">
            <span className="legend-dot" style={{ background: CATEGORY_COLOR[c] }} aria-hidden /> {CATEGORY_LABEL[c]}
          </span>
        ))}
      </p>
      <p className="legend-row">
        <span className="legend-item">
          <span className="legend-line forecast" aria-hidden /> Forecast track
        </span>
        <span className="legend-item">
          <span className="legend-line past" aria-hidden /> Past positions
        </span>
        <span className="legend-item">
          <span className="legend-line previous" aria-hidden /> Previous forecast
        </span>
        <span className="legend-item">
          <span className="legend-swatch cone" aria-hidden /> Cone
        </span>
      </p>
      <p className="legend-row">
        Risk band:
        {RISK_BANDS.map((b) => (
          <span key={b} className="legend-item">
            <span className="legend-dot" style={{ background: RISK_BAND_COLOR[b] }} aria-hidden /> {RISK_BAND_LABEL[b]}
          </span>
        ))}
      </p>
      <p className="legend-row">
        <span className="legend-item">
          <span className="legend-icon hospital" aria-hidden /> Hospital
        </span>
        <span className="legend-item">
          <span className="legend-icon shelter" aria-hidden /> Shelter
        </span>
        <span className="legend-item">
          <span className="legend-icon plant" aria-hidden /> Treatment plant
        </span>
        <span className="legend-item">
          <span className="legend-icon staging" aria-hidden /> Staging area
        </span>
        <span className="legend-item">
          <span className="legend-icon ring" aria-hidden /> Low data confidence
        </span>
      </p>
      <p className="hint small">Size = consequence. Times are local ({LOCAL_TIME_NAME}). Click an asset to see why.</p>
    </div>
  )
}
