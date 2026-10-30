import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import type { DecisionPackage, PackageItem } from '../../types/scenario'
import { PackagePanel } from './PackagePanel'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const proposal: PackageItem = {
  id: 7,
  rule_id: 'P-2.5',
  title: 'Propose activation change at threshold',
  entity_id: 'event',
  entity_name: null,
  kind: 'proposal',
  proposed_action: 'Declare activation Level 2 (prepare), now monitor; the director declares it',
  owner_role: 'director',
  severity: 'high',
  cites: ['P-2.5'],
  overdue: false,
  status: 'pending',
  decided_by: null,
  reason: null,
  decided_at: null,
  blocked_note: null,
}

const pkg: DecisionPackage = {
  advisory_no: 1,
  status: 'open',
  activation_level: 'monitor',
  proposed_activation_level: 'prepare',
  decides_as_commander: 'director',
  changes: {
    advisory_no: 1,
    previous_advisory_no: null,
    landfall_shift: null,
    max_wind_change_mph: null,
    peak_surge_change_m: null,
    activation_level_from: null,
    activation_level_to: 'monitor',
    top10_entered: [],
    top10_left: [],
    rank_moves: [],
  },
  items: [proposal],
  draft: null,
  draft_text: null,
  sitrep: null,
}

const declared: DecisionPackage = {
  ...pkg,
  activation_level: 'prepare',
  items: [{ ...proposal, status: 'approved', decided_by: 'director', decided_at: '2026-10-29T18:05:00Z' }],
}

function mockApi(declare: (body: unknown) => Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/clauses')) return json([])
    if (path.endsWith('/activation/declare')) return declare(JSON.parse(String(init?.body)))
    return json(pkg)
  })
}

const props = { advisoryNo: 1, hoursToLandfall: 72, assetsById: new Map(), onSelectAsset: () => {} }

test('declaring sends the level and role, then shows the declaration and tells the header', async () => {
  const declare = vi.fn(() => json(declared))
  mockApi(declare)
  const onDeclared = vi.fn()
  render(<PackagePanel {...props} role="director" onDeclared={onDeclared} />)

  await userEvent.click(await screen.findByRole('button', { name: 'Declare Level 2' }))

  expect(declare).toHaveBeenCalledWith({ level: 'prepare', declared_by: 'director' })
  expect(await screen.findByText(/Declared by Director/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Declare/ })).not.toBeInTheDocument()
  expect(onDeclared).toHaveBeenCalledOnce()
})

test('a refused declaration shows the reason and changes nothing', async () => {
  mockApi(() => json({ error: { code: 'decision_refused', message: 'Level 2 (prepare) is declared by the director (P-2.5).' } }, 403))
  const onDeclared = vi.fn()
  render(<PackagePanel {...props} role="director" onDeclared={onDeclared} />)

  await userEvent.click(await screen.findByRole('button', { name: 'Declare Level 2' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('declared by the director')
  expect(screen.getByRole('button', { name: 'Declare Level 2' })).toBeEnabled()
  expect(onDeclared).not.toHaveBeenCalled()
})

test('a package that fails to load offers a retry', async () => {
  let calls = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (String(input).endsWith('/clauses')) return json([])
    calls += 1
    return calls === 1 ? json({ error: { code: 'unknown', message: 'boom' } }, 500) : json(pkg)
  })
  render(<PackagePanel {...props} role="director" onDeclared={() => {}} />)

  await userEvent.click(await screen.findByRole('button', { name: 'Retry' }))

  expect(await screen.findByRole('region', { name: 'Activation proposal' })).toBeInTheDocument()
})
