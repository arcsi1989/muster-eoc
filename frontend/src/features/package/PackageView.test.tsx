import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import type { DecisionPackage, PackageItem } from '../../types/scenario'
import { PackageView } from './PackageView'

const item = (overrides: Partial<PackageItem> & Pick<PackageItem, 'id' | 'rule_id' | 'entity_id'>): PackageItem => ({
  title: 'A rule',
  entity_name: null,
  kind: 'gap',
  proposed_action: 'Do the thing',
  owner_role: 'logistics',
  severity: 'high',
  cites: [overrides.rule_id],
  overdue: false,
  status: 'pending',
  decided_by: null,
  reason: null,
  decided_at: null,
  ...overrides,
})

const pkg = (items: PackageItem[], status: 'open' | 'closed' = 'open'): DecisionPackage => ({
  advisory_no: 5,
  status,
  activation_level: 'full',
  decides_as_commander: 'incident_commander',
  changes: {
    advisory_no: 5,
    previous_advisory_no: 4,
    landfall_shift: null,
    max_wind_change_mph: 5,
    peak_surge_change_m: 0.5,
    activation_level_from: 'full',
    activation_level_to: 'full',
    top10_entered: [],
    top10_left: [],
    rank_moves: [],
  },
  items,
  draft: {
    status: 'DRAFT',
    provider: 'template',
    prompt_version: 'template-v1',
    sections: [{ heading: 'Situation', paragraphs: [{ text: 'Advisory 5, 24 h to landfall.', clause_ids: [], asset_ids: [] }] }],
    model: null,
    fallback: false,
    fallback_reason: null,
  },
  draft_text: 'Situation\n\nAdvisory 5, 24 h to landfall.',
  sitrep: null,
})

const sitrepProps = {
  sitrepOpen: true,
  clauses: new Map(),
  sitrepError: null,
  onApproveSitrep: () => {},
  onSelectAsset: () => {},
}

const sub07 = item({
  id: 1,
  rule_id: 'P-4.5',
  entity_id: 'SUB-07',
  entity_name: 'Medical District Substation',
  proposed_action: 'Assign a portable generator to SUB-07 Medical District Substation (feeds HOSP-01)',
})
const conflict = item({
  id: 2,
  rule_id: 'P-4.2',
  entity_id: 'PS-14',
  kind: 'conflict',
  owner_role: 'incident_commander',
  severity: 'critical',
  cites: ['P-4.2', 'P-4.7', 'P-8.2'],
})

test('approving a gap sends the decision', async () => {
  const onDecide = vi.fn()
  render(<PackageView pkg={pkg([sub07])} assetsById={new Map()} busy={false} error={null} {...sitrepProps} onDecide={onDecide} />)

  expect(screen.getByText(/1 of 1 items await a decision/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Approve' }))

  expect(onDecide).toHaveBeenCalledWith(sub07, 'approve', undefined)
})

test('an override needs a reason before it can be sent', async () => {
  const onDecide = vi.fn()
  render(<PackageView pkg={pkg([sub07])} assetsById={new Map()} busy={false} error={null} {...sitrepProps} onDecide={onDecide} />)

  await userEvent.click(screen.getByRole('button', { name: 'Override…' }))
  const send = screen.getByRole('button', { name: 'Override' })
  expect(send).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Reason'), 'crew shortage')
  await userEvent.click(send)

  expect(onDecide).toHaveBeenCalledWith(sub07, 'override', 'crew shortage')
})

test('a conflict offers defer or an alternative measure, never approve', async () => {
  const onDecide = vi.fn()
  render(<PackageView pkg={pkg([conflict])} assetsById={new Map()} busy={false} error={null} {...sitrepProps} onDecide={onDecide} />)

  const section = screen.getByRole('region', { name: 'Conflicts' })
  expect(within(section).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(within(section).getByText('P-4.7')).toBeInTheDocument()
  await userEvent.click(within(section).getByRole('button', { name: 'Defer…' }))
  await userEvent.type(within(section).getByLabelText('Reason'), 'stop-work in force')
  await userEvent.click(within(section).getByRole('button', { name: 'Defer' }))

  expect(onDecide).toHaveBeenCalledWith(conflict, 'defer', 'stop-work in force')
})

test('shows decided items, refusals, and the draft situation report', () => {
  const decided = { ...sub07, status: 'approved' as const, decided_by: 'logistics' }
  render(
    <PackageView
      pkg={pkg([decided])}
      assetsById={new Map()}
      busy={false}
      {...sitrepProps}
      error={{ itemId: 1, error: new ApiError(403, 'decision_refused', 'Only the Incident Commander decides a conflict (P-8.2).') }}
      onDecide={() => {}}
    />,
  )

  expect(screen.getByText('Approved')).toBeInTheDocument()
  expect(screen.getByText(/decided by Logistics/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Only the Incident Commander')
  expect(screen.getByText('DRAFT')).toBeInTheDocument()
  expect(screen.getByText('Advisory 5, 24 h to landfall.')).toBeInTheDocument()
})

test('no decision buttons while a decision is being sent', () => {
  render(<PackageView pkg={pkg([sub07])} assetsById={new Map()} busy error={null} {...sitrepProps} onDecide={() => {}} />)

  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
})

test('conflicts are grouped by rule and the package shows what changed', () => {
  render(<PackageView pkg={pkg([conflict])} assetsById={new Map()} busy={false} error={null} {...sitrepProps} onDecide={() => {}} />)

  const section = screen.getByRole('region', { name: 'Conflicts' })
  expect(within(section).getByText(/A rule · 1/)).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'What changed' })).getByText(/No change/)).toBeInTheDocument()
})

test('a closed package offers no decisions', () => {
  render(<PackageView pkg={pkg([{ ...sub07, status: 'not_decided' }], 'closed')} assetsById={new Map()} busy={false} error={null} {...sitrepProps} onDecide={() => {}} />)

  expect(screen.getByText(/package is closed/)).toBeInTheDocument()
  expect(screen.getByText('Not decided')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Approve$|Override|Defer/ })).not.toBeInTheDocument()
})
