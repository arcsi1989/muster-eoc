import type { TraceSpan } from '../../types/scenario'

/** Idle time between spans (a person deciding before await_approval resumes, or before asking
 * the copilot) is drawn at most this share of the busy time, so the waterfall shows the agent's
 * work rather than the wait. */
const IDLE_GAP_SHARE = 0.1

export interface WaterfallRow {
  span: TraceSpan
  /** 0 for a top-level span, 1 for a generation inside its node */
  depth: number
  /** start and length on the time axis, in percent */
  left: number
  width: number
}

/** Where idle time was shortened, in percent of the axis, and how long it really was. */
export interface WaterfallBreak {
  at: number
  idleMs: number
}

/** Lays an advisory's spans out as a waterfall: each span after its parent, in start order, on
 * one time axis whose idle stretches are shortened to a share of the time the top-level spans were
 * busy. */
export function layoutWaterfall(spans: TraceSpan[]): { rows: WaterfallRow[]; breaks: WaterfallBreak[] } {
  if (spans.length === 0) return { rows: [], breaks: [] }
  const ids = new Set(spans.map((s) => s.span_id))
  const start = (s: TraceSpan) => Date.parse(s.started_at)
  const end = (s: TraceSpan) => Date.parse(s.ended_at)
  const byStart = [...spans].sort((a, b) => start(a) - start(b))
  const topLevel = byStart.filter((s) => s.parent_span_id === null || !ids.has(s.parent_span_id))

  // Walk the top-level spans in time, finding the idle stretches between them.
  const origin = start(byStart[0])
  const idles: { from: number; to: number }[] = []
  let reached = origin
  for (const s of topLevel) {
    if (start(s) > reached) idles.push({ from: reached, to: start(s) })
    reached = Math.max(reached, end(s))
  }
  const busy = reached - origin - idles.reduce((sum, i) => sum + i.to - i.from, 0)
  const maxIdle = busy * IDLE_GAP_SHARE
  // Each idle stretch longer than maxIdle is cut back to it.
  const long = idles.filter((i) => i.to - i.from > maxIdle)
  const cuts = long.map((i) => ({ from: i.to, removed: i.to - i.from - maxIdle }))
  const breaks = long.map((i) => ({ from: i.from, idleMs: i.to - i.from }))
  const axis = (t: number) => t - origin - cuts.reduce((sum, c) => (t >= c.from ? sum + c.removed : sum), 0)
  const total = axis(reached) || 1
  const percent = (ms: number) => (ms / total) * 100

  const rows: WaterfallRow[] = []
  const place = (s: TraceSpan, depth: number) => {
    rows.push({ span: s, depth, left: percent(axis(start(s))), width: percent(axis(end(s)) - axis(start(s))) })
    for (const child of byStart) if (child.parent_span_id === s.span_id) place(child, depth + 1)
  }
  for (const s of topLevel) place(s, 0)

  return {
    rows,
    breaks: breaks.map((b) => ({ at: percent(axis(b.from) + maxIdle / 2), idleMs: b.idleMs })),
  }
}

/** How far apart, in percent of the axis, two idle labels must be so their text does not overlap. */
const BREAK_LABEL_MIN_GAP = 25

/** Which idle breaks get their text label: the longest first, each only where no labelled break
 * is nearer than BREAK_LABEL_MIN_GAP. The rest keep the marker, with the duration on hover. */
export function labelBreaks(breaks: WaterfallBreak[]): (WaterfallBreak & { labelled: boolean })[] {
  const labelled: number[] = []
  for (const b of [...breaks].sort((x, y) => y.idleMs - x.idleMs || x.at - y.at)) {
    if (labelled.every((at) => Math.abs(at - b.at) >= BREAK_LABEL_MIN_GAP)) labelled.push(b.at)
  }
  return breaks.map((b) => ({ ...b, labelled: labelled.includes(b.at) }))
}
