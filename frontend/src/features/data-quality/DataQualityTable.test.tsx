import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { DataQualityTable } from './DataQualityTable'

test('lists each file with its counts and the reason for every rejected row', () => {
  render(
    <DataQualityTable
      entries={[
        { file: 'assets.json', sha256: 'a'.repeat(64), loaded_at: '2026-09-01T00:00:00Z', rows_ok: 196, rows_rejected: 0, issues: [] },
        {
          file: 'assets_rejected_example.json',
          sha256: 'b'.repeat(64),
          loaded_at: '2026-09-01T00:00:00Z',
          rows_ok: 0,
          rows_rejected: 2,
          issues: [
            { row: 0, record_id: 'SUB-121', reason: 'customers_served: Input should be greater than or equal to 0' },
            { row: 1, record_id: 'SUB-122', reason: "type: Input should be 'substation', 'pump_station' or 'treatment_plant'" },
          ],
        },
      ]}
    />,
  )

  const rows = screen.getAllByRole('row')
  expect(within(rows[1]).getByText('assets.json')).toBeInTheDocument()
  expect(within(rows[1]).getByText('196')).toBeInTheDocument()
  expect(within(rows[2]).getByText(/Row 0 \(SUB-121\): customers_served/)).toBeInTheDocument()
  expect(within(rows[2]).getByText(/Row 1 \(SUB-122\): type/)).toBeInTheDocument()
})

test('says so when nothing was loaded', () => {
  render(<DataQualityTable entries={[]} />)

  expect(screen.getByText(/no files were loaded/i)).toBeInTheDocument()
})
