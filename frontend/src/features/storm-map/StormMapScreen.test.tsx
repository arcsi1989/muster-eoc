import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { makeAsset, makeDistrictForecast, makeForecast, makeRiskItem } from '../../test/fixtures'
import type { Advisory, District, RiskList, Scenario, TrackPoint } from '../../types/scenario'
import { StormMapScreen } from './StormMapScreen'
import { CATEGORY_COLOR, RISK_BAND_COLOR } from './stormTrack'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const ISSUED = ['2026-09-01T03:00:00Z', '2026-09-01T15:00:00Z']

const point = (issued: string, t_hours: number, vmax_mph: number, category: TrackPoint['category']): TrackPoint => ({
  t_hours,
  x_km: 40 * t_hours,
  y_km: -400 + 10 * t_hours,
  valid_at: new Date(Date.parse(issued) + t_hours * 3_600_000).toISOString(),
  vmax_mph,
  category,
  rmax_km: 37,
})

const advisory = (no: number): Advisory => {
  const issued = ISSUED[no - 1]
  return {
    advisory_no: no,
    issued_at: issued,
    hours_to_landfall: 72 - 12 * (no - 1),
    activation_level: no === 1 ? 'monitor' : 'prepare',
    max_wind_mph: 130,
    peak_surge_m: 2.5,
    landfall: { x_km: 80, y_km: 57 },
    track: [point(issued, 0, 70, 'tropical_storm'), point(issued, 6, 100, 'cat_2'), point(issued, 12, 130, 'cat_4')],
    past_positions: [],
    cone: [
      { x_km: 0, y_km: -400 },
      { x_km: 500, y_km: -280 },
      { x_km: 400, y_km: -250 },
    ],
  }
}

const scenario = (current: number): Scenario => ({
  total_advisories: 2,
  current_advisory: current,
  timeline: [1, 2].map((no) => ({
    advisory_no: no,
    hours_to_landfall: 72 - 12 * (no - 1),
    activation_level: no <= current ? advisory(no).activation_level : null,
    issued: no <= current,
  })),
  advisories: [1, 2].filter((no) => no <= current).map(advisory),
})

const risk = (no: number, order: string[]): RiskList => ({
  advisory_no: no,
  model_version: 1,
  items: order.map((id, i) => makeRiskItem({ asset_id: id, rank: i + 1 })),
})

const ASSETS = [
  makeAsset({ id: 'PS-14', name: 'Seawall Pumping Station', type: 'pump_station' }),
  makeAsset({ id: 'SUB-01', name: 'Harbour Substation', type: 'substation' }),
]

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

const forecast = (no: number) =>
  makeForecast(
    no,
    DISTRICTS.map((d, i) =>
      makeDistrictForecast({
        district: d.name,
        power_customers: { p50: 1000 * no * i, p90: 10_000 * no * (i + 1) },
        crews_available: 4,
      }),
    ),
  )

function backend(failRiskOnce = false) {
  let current = 1
  let failed = false
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url === '/api/advisories/next' && init?.method === 'POST') return json(scenario(++current))
    if (url === '/api/advisories') return json(scenario(current))
    if (url === '/api/assets') return json(ASSETS)
    if (url === '/api/coastline') return json({ coastline: [], land: [] })
    if (url === '/api/districts') return json(DISTRICTS)
    if (url === '/api/facilities') return json([{ id: 'HOSP-01', name: 'General Hospital', type: 'hospital', x_km: 1, y_km: 1 }])
    if (url === '/api/staging-areas') return json([])
    if (url.startsWith('/api/forecast')) return json(forecast(Number(url.split('=')[1])))
    if (url.startsWith('/api/risk')) {
      if (failRiskOnce && !failed) {
        failed = true
        return json({ error: { code: 'unavailable', message: 'Scores unavailable' } }, 503)
      }
      return json(url.endsWith('=1') ? risk(1, ['PS-14', 'SUB-01']) : risk(2, ['SUB-01', 'PS-14']))
    }
    throw new Error(`unexpected request ${url}`)
  })
}

const rankedIds = () =>
  within(screen.getByRole('region', { name: 'Risk list' }))
    .getAllByRole('button')
    .map((b) => b.textContent?.match(/(PS|SUB)-\d+/)?.[0])

test('the header names the product and the demo scenario', async () => {
  backend()
  render(<StormMapScreen />)

  expect(await screen.findByRole('heading', { level: 1, name: 'Muster' })).toBeInTheDocument()
  expect(screen.getByText('Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)')).toBeInTheDocument()
})

test('the map shows the legend, the cone note and a local-time label on each 12-hour point', async () => {
  backend()
  render(<StormMapScreen />)

  expect(await screen.findByText('Hurricane: Cat 1 to Cat 5, tropical storm')).toBeInTheDocument()
  expect(screen.getByText('Cone shows forecast track uncertainty, not the area that will be impacted.')).toBeInTheDocument()
  // issued 03:00 UTC on Tue 1 Sept: 23:00 Mon and 11:00 Tue at UTC-4; the 6-hour point has no label
  const map = await screen.findByRole('img', { name: 'Storm map, advisory 1' })
  expect(within(map).getByText('23:00 Mon')).toBeInTheDocument()
  expect(within(map).getByText('11:00 Tue')).toBeInTheDocument()
  expect(within(map).queryByText('05:00 Tue')).not.toBeInTheDocument()
})

test('the map names the four served districts and draws a dashed boundary between each pair of neighbours', async () => {
  backend()
  const { container } = render(<StormMapScreen />)
  const map = await screen.findByRole('img', { name: 'Storm map, advisory 1' })

  // a name wider than its district wraps, one word per line
  const labels = [...map.querySelectorAll('.district-label')].map((l) => l.textContent)
  expect(labels).toEqual(['Westshore', 'Bayport West', 'Bayport East', 'Eastern Plains'])
  const boundaries = container.querySelectorAll<SVGPolylineElement>('.district-boundary')
  expect([...boundaries].map((b) => b.getAttribute('points'))).toEqual(['75,-55 75,-220', '135,-55 135,-220', '190,-55 190,-220'])
  expect(boundaries[0].style.strokeDasharray).not.toBe('')
  // drawn before the cone, the track and the assets, so they lie on top
  const order = [...container.querySelectorAll('.districts, .cone, .track-forecast, .asset')]
  expect(order[0].getAttribute('class')).toBe('districts')
  expect(container.querySelectorAll('.cone, .track-forecast, .asset').length).toBeGreaterThanOrEqual(4)
})

test('forecast dots are coloured by intensity category', async () => {
  backend()
  const { container } = render(<StormMapScreen />)
  await screen.findByRole('img', { name: 'Storm map, advisory 1' })

  const dots = container.querySelectorAll<SVGCircleElement>('.track-dot[data-category]')
  expect([...dots].map((d) => d.dataset.category)).toEqual(['tropical_storm', 'cat_2', 'cat_4'])
  expect(dots[2].style.fill).toBe(hexToRgb(CATEGORY_COLOR.cat_4))
})

test('assets show name, type, rank, p_fail and top factor, and a click opens the explanation', async () => {
  backend()
  render(<StormMapScreen />)

  const asset = await screen.findByRole('button', { name: /^PS-14 Seawall Pumping Station, Pump station · rank 1/ })
  expect(asset).toHaveAccessibleName(/p_fail 30% · top factor: wind/)
  await userEvent.click(asset)
  expect(screen.getByRole('complementary', { name: 'Why PS-14 ranks where it does' })).toBeInTheDocument()
})

test('stepping to the next advisory updates the header and reorders the ranked list', async () => {
  backend()
  render(<StormMapScreen />)

  const header = await screen.findByLabelText('Current advisory')
  expect(header).toHaveTextContent('Advisory1')
  expect(header).toHaveTextContent('72 h')
  expect(header).toHaveTextContent('Level 3 · Monitor')
  await screen.findByRole('button', { name: /^1.*PS-14/ })
  expect(rankedIds()).toEqual(['PS-14', 'SUB-01'])

  await userEvent.click(screen.getByRole('button', { name: 'Issue advisory 2 ▶' }))

  expect(await screen.findByLabelText('Current advisory')).toHaveTextContent('Advisory2')
  expect(screen.getByLabelText('Current advisory')).toHaveTextContent('60 h')
  expect(screen.getByLabelText('Current advisory')).toHaveTextContent('Level 2 · Prepare')
  await screen.findByRole('button', { name: /^1.*SUB-01/ })
  expect(rankedIds()).toEqual(['SUB-01', 'PS-14'])
})

test('a failed risk list shows the error with a retry', async () => {
  backend(true)
  render(<StormMapScreen />)

  expect(await screen.findByText(/Could not load the risk list: Scores unavailable/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByRole('button', { name: /^1.*PS-14/ })).toBeInTheDocument()
})

function hexToRgb(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  return `rgb(${r}, ${g}, ${b})`
}

test('the ranked list uses the same risk band colour as the map', async () => {
  backend()
  render(<StormMapScreen />)

  const row = await screen.findByRole('button', { name: /^1.*PS-14/ })
  const swatch = row.querySelector<HTMLElement>('.swatch')!
  expect(swatch.style.background).toBe(hexToRgb(RISK_BAND_COLOR.high))
})

test('the district summary and the map show the outage forecast, and change with each advisory', async () => {
  backend()
  render(<StormMapScreen />)

  const summary = screen.getByRole('region', { name: 'How bad, where' })
  const table = await within(summary).findByRole('table', { name: 'Outage forecast by district, advisory 1' })
  const westshore = within(table).getByRole('row', { name: /^Westshore/ })
  expect(within(westshore).getAllByRole('cell')[0]).toHaveTextContent('power 0–10k')
  expect(within(westshore).getAllByRole('cell')[1]).toHaveTextContent('14–47 / 4 short')
  // the district overlay, in the territory view: each district's customers out at P90, under its name
  const map = screen.getByRole('img', { name: 'Storm map, advisory 1' })
  const outage = () => [...map.querySelectorAll('.district-outage')].map((t) => t.textContent)
  expect(outage()).toEqual([])
  await userEvent.click(screen.getByRole('button', { name: 'Territory' }))
  expect(outage()[0]).toBe('10.0k power 114.8k water out (P90)')
  expect(outage()).toHaveLength(4)

  await userEvent.click(screen.getByRole('button', { name: 'Issue advisory 2 ▶' }))

  expect(await within(summary).findByRole('table', { name: 'Outage forecast by district, advisory 2' })).toBeInTheDocument()
  const bayportWest = within(summary).getByRole('row', { name: /^Bayport West/ })
  expect(within(bayportWest).getAllByRole('cell')[0]).toHaveTextContent('power 2.0k–40k')
  expect(outage()[0]).toBe('20.0k power 114.8k water out (P90)')
})
