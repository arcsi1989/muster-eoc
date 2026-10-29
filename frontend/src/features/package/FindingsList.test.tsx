import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Clause, Finding } from '../../types/scenario'
import { FindingsList } from './FindingsList'

const finding = (overrides: Partial<Finding> & Pick<Finding, 'rule_id' | 'entity_id' | 'status'>): Finding => ({
  title: 'A rule',
  entity_kind: 'asset',
  entity_name: null,
  severity: 'high',
  owner_role: 'operations',
  cites: [overrides.rule_id],
  overdue: false,
  details: {},
  ...overrides,
})

const clauses = new Map<string, Clause>([['P-8.2', { id: 'P-8.2', section: '8', title: 'Conflicting clauses', text: '' }]])

test('groups conflicts, gaps and satisfied findings', () => {
  render(
    <FindingsList
      clauses={clauses}
      findings={[
        finding({
          rule_id: 'P-4.2',
          entity_id: 'PS-14',
          entity_name: 'Seawall Pumping Station',
          status: 'conflict',
          title: 'Pre-inspect coastal pumping stations at flood risk',
          cites: ['P-4.2', 'P-4.7', 'P-8.2'],
          severity: 'critical',
        }),
        finding({
          rule_id: 'P-4.5',
          entity_id: 'SUB-07',
          entity_name: 'Medical District Substation',
          status: 'open',
          owner_role: 'logistics',
          details: { 'asset.feeds_facility_ids': ['HOSP-01'] },
        }),
        finding({ rule_id: 'P-7.2', entity_id: 'event', entity_kind: 'event', status: 'open', overdue: true }),
        finding({ rule_id: 'P-5.2', entity_id: 'PS-03', status: 'satisfied' }),
      ]}
    />,
  )

  const conflicts = screen.getByRole('region', { name: 'Conflicts' })
  expect(within(conflicts).getByText(/Incident Commander decides/)).toBeInTheDocument()
  expect(within(conflicts).getByText('P-4.7')).toBeInTheDocument()
  expect(within(conflicts).getByText('P-8.2')).toHaveAttribute('title', 'Conflicting clauses')
  expect(within(conflicts).getByText(/PS-14 Seawall Pumping Station/)).toBeInTheDocument()

  const gaps = screen.getByRole('region', { name: 'Gaps' })
  expect(within(gaps).getByText(/SUB-07 Medical District Substation · Logistics · Feeds HOSP-01/)).toBeInTheDocument()
  expect(within(gaps).getByText('Overdue')).toBeInTheDocument()
  expect(within(gaps).getByText(/EOC-wide/)).toBeInTheDocument()

  expect(screen.getByText('Satisfied · 1')).toBeInTheDocument()
})

test('says so when no rule applies', () => {
  render(<FindingsList findings={[]} clauses={clauses} />)

  expect(screen.getByText(/no playbook rule applies/i)).toBeInTheDocument()
})
