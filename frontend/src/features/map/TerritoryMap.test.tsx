import { render } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { makeAsset } from '../../test/fixtures'
import type { District } from '../../types/scenario'
import { TerritoryMap } from './TerritoryMap'

const district = (name: string, west_km: number, east_km: number): District => ({
  name,
  west_km,
  east_km,
  label: { x_km: (west_km + east_km) / 2, y_km: 165 },
  boundary: west_km === 0 ? [] : [{ x_km: west_km, y_km: 55 }, { x_km: west_km, y_km: 220 }],
})

const DISTRICTS = [
  district('Westshore', 0, 75),
  district('Bayport West', 75, 135),
  district('Bayport East', 135, 190),
  district('Eastern Plains', 190, 260),
]

const renderMap = () =>
  render(
    <TerritoryMap
      coastline={{ coastline: [], land: [] }}
      districts={DISTRICTS}
      assets={[makeAsset({ id: 'PS-14', name: 'Seawall Pumping Station', type: 'pump_station' })]}
      facilities={[]}
      stagingAreas={[]}
      pFail={new Map()}
      exposure={new Map()}
      advisory={undefined}
      previous={undefined}
      onSelect={vi.fn()}
    />,
  )

test('the operations map names the four served districts and draws a dashed boundary between neighbours', () => {
  const { container } = renderMap()

  const labels = [...container.querySelectorAll('.district-label')].map((l) => l.textContent)
  expect(labels).toEqual(['Westshore', 'Bayport West', 'Bayport East', 'Eastern Plains'])
  // (jsdom keeps no class on Leaflet's SVG paths, so they are found by pane and dash)
  const boundaries = container.querySelectorAll('.leaflet-districts-pane path[stroke-dasharray="6 5"]')
  expect(boundaries).toHaveLength(3)
})

test('the districts sit in a pane below the cone, track and assets', () => {
  const { container } = renderMap()

  const pane = container.querySelector<HTMLElement>('.leaflet-districts-pane')
  const overlay = container.querySelector<HTMLElement>('.leaflet-overlay-pane')
  expect(pane?.querySelector('.district-label')).not.toBeNull()
  // Leaflet's overlay pane (cone, track, asset markers) is at z-index 400 in its stylesheet
  expect(Number(pane?.style.zIndex)).toBeLessThan(400)
  expect(overlay?.querySelector('[stroke-dasharray="6 5"]')).toBeNull()
})
