import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ApiError } from '../../api/client'
import type { PackageItem } from '../../types/scenario'
import { ActivationProposalCard } from './ActivationProposalCard'

const proposal: PackageItem = {
  id: 7,
  rule_id: 'P-2.5',
  title: 'Propose activation change at threshold',
  entity_id: 'event',
  entity_name: null,
  kind: 'proposal',
  proposed_action: 'Declare activation Level 1 (full), now prepare; the incident commander declares it',
  owner_role: 'incident_commander',
  severity: 'high',
  cites: ['P-2.5'],
  overdue: false,
  status: 'pending',
  decided_by: null,
  reason: null,
  decided_at: null,
  blocked_note: null,
}

const props = {
  item: proposal,
  proposed: 'full' as const,
  declared: 'prepare' as const,
  hoursToLandfall: 48,
  packageOpen: true,
  busy: false,
  error: null,
  onDeclare: () => {},
}

test('proposes the level with the reason and lets the declaring role declare it', async () => {
  const onDeclare = vi.fn()
  render(<ActivationProposalCard {...props} role="incident_commander" onDeclare={onDeclare} />)

  expect(screen.getByRole('heading', { name: /Activation proposal: Level 1 · Full activation/ })).toBeInTheDocument()
  expect(screen.getByText(/48 h to landfall/)).toBeInTheDocument()
  expect(screen.getByText(/Declared now: Level 2 · Prepare/)).toBeInTheDocument()
  const user = userEvent.setup({ delay: null }) // no per-key delay: the suite runs beside the backend tests
  await user.type(screen.getByLabelText(/Reason/), 'storm on track')
  await user.click(screen.getByRole('button', { name: 'Declare Level 1' }))

  expect(onDeclare).toHaveBeenCalledWith('full', 'storm on track')
})

test('another role sees who must declare, and no enabled button', () => {
  render(<ActivationProposalCard {...props} role="director" />)

  expect(screen.getByRole('button', { name: 'Declare Level 1' })).toBeDisabled()
  expect(screen.getByText(/Only the Incident Commander declares Level 1/)).toBeInTheDocument()
})

test('the Director declares Level 2', () => {
  const level2 = { ...proposal, owner_role: 'director' }
  render(<ActivationProposalCard {...props} item={level2} proposed="prepare" declared="monitor" role="director" />)

  expect(screen.getByRole('button', { name: 'Declare Level 2' })).toBeEnabled()
})

test('after the declaration the card shows who, when and why, and no button', () => {
  const declared = {
    ...proposal,
    status: 'approved' as const,
    decided_by: 'incident_commander',
    reason: 'storm on track',
    decided_at: '2026-10-29T18:05:00Z',
  }
  render(<ActivationProposalCard {...props} item={declared} declared="full" role="incident_commander" />)

  expect(screen.getByText(/Declared by Incident Commander/)).toBeInTheDocument()
  expect(screen.getByText(/29 Oct, 18:05 UTC/)).toBeInTheDocument()
  expect(screen.getByText(/at T-48 h/)).toBeInTheDocument()
  expect(screen.getByText(/“storm on track”/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Declare/ })).not.toBeInTheDocument()
})

test('a refused or failed declaration shows its error', () => {
  render(
    <ActivationProposalCard
      {...props}
      role="incident_commander"
      error={new ApiError(403, 'decision_refused', 'Level 1 (full) is declared by the incident commander (P-2.5).')}
    />,
  )

  expect(screen.getByRole('alert')).toHaveTextContent('declared by the incident commander')
})

test('no button while the declaration is being sent or once the package is closed', () => {
  const { rerender } = render(<ActivationProposalCard {...props} role="incident_commander" busy />)
  expect(screen.getByRole('button', { name: 'Declare Level 1' })).toBeDisabled()

  rerender(<ActivationProposalCard {...props} role="incident_commander" packageOpen={false} />)
  expect(screen.queryByRole('button', { name: /Declare/ })).not.toBeInTheDocument()
  expect(screen.getByText(/not declared/)).toBeInTheDocument()
})
