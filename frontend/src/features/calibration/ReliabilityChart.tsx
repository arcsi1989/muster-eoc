import type { ReliabilityBin } from '../../types/scenario'

/** One model's reliability bins, with the label its curve and legend show. */
export interface ReliabilitySeries {
  label: string
  reliability: ReliabilityBin[]
}

interface Props {
  /** drawn in the two series colours, first then second */
  first: ReliabilitySeries
  second: ReliabilitySeries
}

const SIZE = 320
const PAD = 40
const PLOT = SIZE - 2 * PAD
const TICKS = [0, 0.25, 0.5, 0.75, 1]

const x = (p: number) => PAD + p * PLOT
const y = (rate: number) => SIZE - PAD - rate * PLOT

/** Mean predicted against observed failure rate per bin; empty bins have no point. */
function points(reliability: ReliabilityBin[]): [number, number][] {
  return reliability.flatMap((b) =>
    b.mean_predicted === null || b.observed_rate === null ? [] : [[x(b.mean_predicted), y(b.observed_rate)]],
  )
}

function Curve({ series, className }: { series: ReliabilitySeries; className: string }) {
  const pts = points(series.reliability)
  return (
    <g aria-label={series.label} className={className}>
      <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" />
      {pts.map(([cx, cy]) => (
        <circle key={`${cx},${cy}`} cx={cx} cy={cy} r={3.5} />
      ))}
    </g>
  )
}

/** Two reliability curves on one chart, with the diagonal: a calibration run's before and after,
 * or the champion and the challenger. */
export function ReliabilityChart({ first, second }: Props) {
  return (
    <figure className="reliability">
      <svg
        role="img"
        aria-label={`Reliability chart, ${first.reliability.length} bins: ${first.label}, ${second.label}`}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
      >
        {TICKS.map((t) => (
          <g key={t} className="reliability-grid">
            <line x1={x(t)} y1={y(0)} x2={x(t)} y2={y(1)} />
            <line x1={x(0)} y1={y(t)} x2={x(1)} y2={y(t)} />
            <text x={x(t)} y={y(0) + 14} textAnchor="middle">
              {t}
            </text>
            <text x={x(0) - 6} y={y(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        <line aria-label="Perfect calibration" className="reliability-diagonal" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
        <Curve series={first} className="reliability-first" />
        <Curve series={second} className="reliability-second" />
        <text className="reliability-axis" x={x(0.5)} y={SIZE - 6} textAnchor="middle">
          Predicted failure probability
        </text>
        <text className="reliability-axis" transform={`translate(10 ${y(0.5)}) rotate(-90)`} textAnchor="middle">
          Observed failure rate
        </text>
      </svg>
      <figcaption className="hint small">
        <span className="legend-swatch reliability-first" /> {first.label}{' '}
        <span className="legend-swatch reliability-second" /> {second.label}{' '}
        <span className="legend-swatch reliability-diagonal" /> Perfect calibration
      </figcaption>
    </figure>
  )
}
