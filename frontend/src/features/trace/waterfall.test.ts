import { expect, test } from 'vitest'
import { makeSpan } from './traceFixtures'
import { layoutWaterfall } from './waterfall'

test('places each span on one time axis, as a share of the advisory trace', () => {
  const { rows, breaks } = layoutWaterfall([
    makeSpan({ span_id: 'a', node: 'ingest' }, 0, 100),
    makeSpan({ span_id: 'b', node: 'score' }, 100, 300),
  ])

  expect(rows.map((r) => [r.span.node, r.left, r.width])).toEqual([
    ['ingest', 0, 25],
    ['score', 25, 75],
  ])
  expect(breaks).toEqual([])
})

test('nests a generation under its node, whatever order the spans come in', () => {
  const { rows } = layoutWaterfall([
    makeSpan({ span_id: 'draft', node: 'draft' }, 0, 1000),
    makeSpan({ span_id: 'after', node: 'await_approval' }, 1000, 1000),
    makeSpan({ span_id: 'gen', node: 'sitrep_draft', kind: 'generation', parent_span_id: 'draft' }, 200, 500),
  ])

  expect(rows.map((r) => [r.span.node, r.depth, r.left, r.width])).toEqual([
    ['draft', 0, 0, 50],
    ['sitrep_draft', 1, 10, 25],
    ['await_approval', 0, 50, 50],
  ])
})

test('a span whose parent is not in the trace (the HTTP request) is top level', () => {
  const { rows } = layoutWaterfall([
    makeSpan({ span_id: 'turn', node: 'copilot', kind: 'generation', parent_span_id: 'http' }, 0, 100),
  ])

  expect(rows).toEqual([expect.objectContaining({ depth: 0, left: 0, width: 100 })])
})

test('shortens idle time between spans to a fixed gap and marks where', () => {
  // the cycle, then a decision two minutes later resumes await_approval
  const { rows, breaks } = layoutWaterfall(
    [
      makeSpan({ span_id: 'a', node: 'draft' }, 0, 400),
      makeSpan({ span_id: 'b', node: 'await_approval' }, 120_400, 400),
    ],
    200,
  )

  expect(rows.map((r) => [r.left, r.width])).toEqual([
    [0, 40],
    [60, 40],
  ])
  expect(breaks).toEqual([{ at: 50, idleMs: 120_000 }])
})

test('by default idle time is drawn at most a tenth of the busy time', () => {
  const { rows, breaks } = layoutWaterfall([
    makeSpan({ span_id: 'a', node: 'draft' }, 0, 500),
    makeSpan({ span_id: 'b', node: 'copilot' }, 60_500, 500),
    makeSpan({ span_id: 'c', node: 'copilot' }, 61_010, 90),
  ])

  // busy 1090 ms: the minute-long wait shows as 109 ms, the 10 ms pause stays; the axis is 1209 ms
  expect(rows.map((r) => r.left)).toEqual([0, (609 / 1209) * 100, (1119 / 1209) * 100])
  expect(breaks).toHaveLength(1)
})

test('an empty trace has no rows; a zero-length trace does not divide by zero', () => {
  expect(layoutWaterfall([])).toEqual({ rows: [], breaks: [] })
  const { rows } = layoutWaterfall([makeSpan({ span_id: 'a', node: 'ingest' }, 0, 0)])
  expect(rows).toEqual([expect.objectContaining({ left: 0, width: 0 })])
})
