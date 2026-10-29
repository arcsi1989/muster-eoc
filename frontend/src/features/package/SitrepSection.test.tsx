import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Clause, Draft } from '../../types/scenario'
import { SitrepSection } from './SitrepSection'

const draft: Draft = {
  status: 'DRAFT',
  provider: 'anthropic',
  fallback: false,
  model: 'claude-sonnet-5-5',
  prompt_version: 'sitrep-v2',
  fallback_reason: null,
  sections: [
    {
      heading: 'Conflicts for the Incident Commander',
      paragraphs: [{ text: 'PS-14 cannot be inspected safely.', clause_ids: ['P-4.2', 'P-8.2'], asset_ids: ['PS-14'] }],
    },
  ],
}
const clauses = new Map<string, Clause>([
  ['P-8.2', { id: 'P-8.2', section: '8', title: 'Conflicting clauses', text: 'Where two clauses cannot both be met, the safety of personnel prevails.' }],
])
const base = {
  draft,
  draftText: 'Conflicts for the Incident Commander\n\nPS-14 cannot be inspected safely.',
  sitrep: null,
  open: true,
  clauses,
  error: null,
  busy: false,
  onApprove: () => {},
  onSelectAsset: () => {},
}

test('labels the AI draft and shows its citations as chips', async () => {
  const onSelectAsset = vi.fn()
  render(<SitrepSection {...base} onSelectAsset={onSelectAsset} />)

  expect(screen.getByText('DRAFT')).toBeInTheDocument()
  expect(screen.getByText(/AI draft \(claude-sonnet-5-5\)/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'P-8.2' }))
  expect(screen.getByRole('complementary', { name: 'Clause P-8.2' })).toHaveTextContent('safety of personnel prevails')
  await userEvent.click(screen.getByRole('button', { name: 'PS-14' }))
  expect(onSelectAsset).toHaveBeenCalledWith('PS-14')
})

test('the commander can edit before approving', async () => {
  const onApprove = vi.fn()
  render(<SitrepSection {...base} onApprove={onApprove} />)

  await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
  await userEvent.type(screen.getByLabelText('Situation report text'), ' Crews withdrawn.')
  await userEvent.click(screen.getByRole('button', { name: 'Approve situation report' }))

  expect(onApprove).toHaveBeenCalledWith(`${base.draftText} Crews withdrawn.`)
})

test('a fallback draft says why the AI draft was not used', () => {
  render(<SitrepSection {...base} draft={{ ...draft, provider: 'template (fallback)', fallback: true, fallback_reason: 'citations failed validation: clause P-9.9' }} />)

  expect(screen.getByText(/the AI draft was not used/)).toBeInTheDocument()
  expect(screen.getByText(/P-9.9/)).toBeInTheDocument()
})

test('an approved report shows who approved it and whether it was edited', () => {
  render(
    <SitrepSection
      {...base}
      sitrep={{ advisory_no: 5, approved_text: 'Final text.', approved_by: 'incident_commander', approved_at: '2026-09-03T03:00:00Z', edited: true }}
    />,
  )

  expect(screen.getByText('Approved')).toBeInTheDocument()
  expect(screen.getByText(/Approved by Incident Commander, edited from the draft/)).toBeInTheDocument()
  expect(screen.getByText('Final text.')).toBeInTheDocument()
})
