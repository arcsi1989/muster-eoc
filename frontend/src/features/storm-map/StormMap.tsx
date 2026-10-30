import { useState } from 'react'
import { formatPercent } from '../../lib/format'
import type { Advisory, Asset, AssetType, Coastline, Facility, Point, RiskItem, StagingArea } from '../../types/scenario'
import { CATEGORY_COLOR, CATEGORY_LABEL, formatLocalTime, LABEL_EVERY_H, RISK_BAND_COLOR, timeLabels } from './stormTrack'

// Plain SVG on the planar km grid: x = x_km, y = -y_km (north up). No tiles, no real geography.
const VIEWS = {
  storm: { x: -340, y: -280, width: 940, height: 560, label: 'Storm' },
  territory: { x: -40, y: -235, width: 340, height: 300, label: 'Territory' },
} as const
type View = keyof typeof VIEWS

/** Sizes below are for a view this many km tall; other views scale them to look the same. */
const REFERENCE_HEIGHT_KM = 560
const FONT_SIZE = 13
/** Asset radius: the smallest, plus up to this much more as consequence grows (area tracks it). */
const ASSET_R_MIN = 2.5
const ASSET_R_SPAN = 5
/** A time label's box, in font sizes, for the collision check. */
const LABEL_BOX = { width: 6, height: 1.3 }

const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  substation: 'Substation',
  pump_station: 'Pump station',
  treatment_plant: 'Treatment plant',
}

const path = (points: Point[]) => points.map((p) => `${p.x_km},${-p.y_km}`).join(' ')

interface Hover {
  at: Point
  lines: string[]
}

interface Props {
  coastline: Coastline
  assets: Asset[]
  facilities: Facility[]
  stagingAreas: StagingArea[]
  /** the current advisory; nothing to draw for the storm before advisory 1 */
  advisory: Advisory | undefined
  previous: Advisory | undefined
  risk: Map<string, RiskItem>
  onSelect: (assetId: string) => void
}

export function StormMap({ coastline, assets, facilities, stagingAreas, advisory, previous, risk, onSelect }: Props) {
  const [view, setView] = useState<View>('storm')
  const [hover, setHover] = useState<Hover | null>(null)
  const box = VIEWS[view]
  // Markers and text keep their on-screen size whichever view is shown.
  const scale = box.height / REFERENCE_HEIGHT_KM
  const font = FONT_SIZE * scale
  const maxConsequence = Math.max(1, ...Array.from(risk.values(), (r) => r.consequence))
  const hoverProps = (at: Point, lines: string[]) => ({
    onMouseEnter: () => setHover({ at, lines }),
    onMouseLeave: () => setHover(null),
    onFocus: () => setHover({ at, lines }),
    onBlur: () => setHover(null),
  })

  return (
    <div className="storm-map">
      <div className="storm-map-views" role="group" aria-label="Map view">
        {(Object.keys(VIEWS) as View[]).map((v) => (
          <button key={v} type="button" className="secondary" aria-pressed={view === v} onClick={() => setView(v)}>
            {VIEWS[v].label}
          </button>
        ))}
      </div>
      <svg
        className="storm-map-canvas"
        viewBox={`${box.x} ${box.y} ${box.width} ${box.height}`}
        role="img"
        aria-label={advisory ? `Storm map, advisory ${advisory.advisory_no}` : 'Storm map, no advisory issued'}
        style={{ fontSize: font }}
      >
        <polygon className="land" points={path(coastline.land)} />
        <polyline className="coast" points={path(coastline.coastline)} style={{ strokeWidth: 2 * scale }} />

        {advisory && previous && (
          // The outgoing advisory's cone and track fade out while the new ones fade in.
          <g key={`out-${previous.advisory_no}`} className="storm-fade-out" aria-hidden>
            <polygon className="cone" points={path(previous.cone)} />
            <polyline
              className="track-forecast"
              points={path(previous.track)}
              style={{ strokeWidth: 2.5 * scale, strokeDasharray: `${8 * scale} ${6 * scale}` }}
            />
          </g>
        )}
        {advisory && (
          <g key={advisory.advisory_no} className="storm-redraw">
            <polygon className="cone" points={path(advisory.cone)} />
            {previous && (
              <polyline className="track-previous" points={path(previous.track)} style={{ strokeWidth: 1.5 * scale }}>
                <title>Advisory {previous.advisory_no} forecast track</title>
              </polyline>
            )}
            <polyline
              className="track-past"
              points={path([...advisory.past_positions, advisory.track[0]])}
              style={{ strokeWidth: 2.5 * scale }}
            />
            <polyline
              className="track-forecast"
              points={path(advisory.track)}
              style={{ strokeWidth: 2.5 * scale, strokeDasharray: `${8 * scale} ${6 * scale}` }}
            />
          </g>
        )}
        {advisory?.past_positions.map((p) => (
          <circle
            key={`past-${p.advisory_no}`}
            className="track-dot past storm-redraw"
            cx={p.x_km}
            cy={-p.y_km}
            r={3.5 * scale}
            fill={CATEGORY_COLOR[p.category]}
          />
        ))}
        {advisory?.track.map((p) => (
          <circle
            key={p.valid_at}
            className="track-dot"
            data-category={p.category}
            r={(p.t_hours % LABEL_EVERY_H === 0 ? 5 : 3) * scale}
            style={{ transform: `translate(${p.x_km}px, ${-p.y_km}px)`, fill: CATEGORY_COLOR[p.category] }}
            {...hoverProps(p, [`${formatLocalTime(p.valid_at)} · ${CATEGORY_LABEL[p.category]}`, `${p.vmax_mph} mph`])}
          />
        ))}
        {stagingAreas.map((area) => {
          const s = 6 * scale
          return (
            <polygon
              key={area.id}
              className="icon staging"
              points={`${area.x_km},${-area.y_km - s} ${area.x_km + s},${-area.y_km} ${area.x_km},${-area.y_km + s} ${area.x_km - s},${-area.y_km}`}
              tabIndex={0}
              aria-label={`${area.id} ${area.name}, staging area`}
              {...hoverProps(area, [`${area.id} ${area.name}`, 'Staging area'])}
            />
          )
        })}
        {facilities.map((f) => {
          const s = 4.5 * scale
          const x = f.x_km
          const y = -f.y_km
          const label = f.type === 'hospital' ? 'Hospital' : 'Shelter'
          return (
            <g
              key={f.id}
              className={`icon facility-${f.type}`}
              tabIndex={0}
              aria-label={`${f.id} ${f.name}, ${label.toLowerCase()}`}
              {...hoverProps(f, [`${f.id} ${f.name}`, label])}
            >
              {f.type === 'hospital' ? (
                <>
                  <rect x={x - s} y={y - s} width={2 * s} height={2 * s} />
                  <path d={`M${x} ${y - s * 0.65}V${y + s * 0.65}M${x - s * 0.65} ${y}H${x + s * 0.65}`} />
                </>
              ) : (
                <polygon points={`${x},${y - s * 1.2} ${x + s},${y + s * 0.8} ${x - s},${y + s * 0.8}`} />
              )}
            </g>
          )
        })}
        {assets.map((asset) => {
          const item = risk.get(asset.id)
          const r = scale * (ASSET_R_MIN + ASSET_R_SPAN * Math.sqrt((item?.consequence ?? 0) / maxConsequence))
          const x = asset.x_km
          const y = -asset.y_km
          const fill = item ? RISK_BAND_COLOR[item.risk_band] : undefined
          const lines = [
            `${asset.id} ${asset.name}`,
            item ? `${ASSET_TYPE_LABEL[asset.type]} · rank ${item.rank}` : ASSET_TYPE_LABEL[asset.type],
            ...(item ? [`p_fail ${formatPercent(item.p_fail)} · top factor: ${item.top_factor}`] : []),
          ]
          return (
            <g
              key={asset.id}
              className={`icon asset asset-${asset.type}`}
              data-band={item?.risk_band ?? 'unscored'}
              role="button"
              tabIndex={0}
              aria-label={lines.join(', ')}
              onClick={() => onSelect(asset.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(asset.id)
                }
              }}
              {...hoverProps(asset, lines)}
            >
              {item?.confidence === 'low' && (
                <circle className="low-confidence" cx={x} cy={y} r={r + 2.5 * scale} style={{ strokeWidth: 1.2 * scale }} />
              )}
              {asset.type === 'treatment_plant' ? (
                <rect className="asset-shape" x={x - r} y={y - r} width={2 * r} height={2 * r} style={{ fill }} />
              ) : (
                <circle className="asset-shape" cx={x} cy={y} r={r} style={{ fill }} />
              )}
            </g>
          )
        })}

        {advisory &&
          timeLabels(advisory.track, { width: LABEL_BOX.width * font, height: LABEL_BOX.height * font }).map((p) => (
            <text
              key={p.valid_at}
              className="time-label"
              style={{ transform: `translate(${p.x_km + 8 * scale}px, ${-p.y_km + 4 * scale}px)` }}
            >
              {formatLocalTime(p.valid_at)}
            </text>
          ))}

        {hover && <HoverCard hover={hover} scale={scale} font={font} />}
      </svg>
      {!advisory && <p className="storm-map-empty">Issue advisory 1 to see the forecast track and cone.</p>}
    </div>
  )
}

function HoverCard({ hover, scale, font }: { hover: Hover; scale: number; font: number }) {
  const width = Math.max(...hover.lines.map((l) => l.length)) * font * 0.56 + 12 * scale
  const height = hover.lines.length * font * 1.3 + 8 * scale
  const x = hover.at.x_km + 10 * scale
  const y = -hover.at.y_km - height - 6 * scale
  return (
    <g className="hover-card" pointerEvents="none">
      <rect x={x} y={y} width={width} height={height} rx={4 * scale} />
      {hover.lines.map((line, i) => (
        <text key={i} x={x + 6 * scale} y={y + 4 * scale + (i + 1) * font * 1.15}>
          {line}
        </text>
      ))}
    </g>
  )
}
