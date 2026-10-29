import type { IntensityCategory, RiskBand, TrackPoint } from '../../types/scenario'

/** The fictional territory's local time: a fixed UTC-4, so no real place is named. */
export const LOCAL_TIME_ZONE = 'Etc/GMT+4'
export const LOCAL_TIME_NAME = 'UTC−4'

const localFormat = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: LOCAL_TIME_ZONE,
})

/** "07:00 Thu", as on an NHC track graphic. */
export function formatLocalTime(iso: string): string {
  const parts = Object.fromEntries(localFormat.formatToParts(new Date(iso)).map((p) => [p.type, p.value]))
  return `${parts.hour}:${parts.minute} ${parts.weekday}`
}

/** Hours between labelled forecast points. */
export const LABEL_EVERY_H = 12

const collides = (a: TrackPoint, b: TrackPoint, box: { width: number; height: number }) =>
  Math.abs(a.x_km - b.x_km) < box.width && Math.abs(a.y_km - b.y_km) < box.height

/** The 12-hour forecast points that get a time label; while neighbours' labels (a box in km)
 * would overlap, only every other one keeps its label. */
export function timeLabels(track: TrackPoint[], box: { width: number; height: number }): TrackPoint[] {
  let labelled = track.filter((p) => p.t_hours % LABEL_EVERY_H === 0)
  while (labelled.length > 1 && labelled.some((p, i) => i > 0 && collides(labelled[i - 1], p, box))) {
    labelled = labelled.filter((_, i) => i % 2 === 0)
  }
  return labelled
}

/** Display order of the legend, weakest first. */
export const CATEGORIES: IntensityCategory[] = [
  'tropical_depression',
  'tropical_storm',
  'cat_1',
  'cat_2',
  'cat_3',
  'cat_4',
  'cat_5',
]

export const CATEGORY_LABEL: Record<IntensityCategory, string> = {
  tropical_depression: 'Tropical depression',
  tropical_storm: 'Tropical storm',
  cat_1: 'Cat 1',
  cat_2: 'Cat 2',
  cat_3: 'Cat 3',
  cat_4: 'Cat 4',
  cat_5: 'Cat 5',
}

/** Saffir-Simpson colours in the style of NHC and most broadcasters' track graphics. */
export const CATEGORY_COLOR: Record<IntensityCategory, string> = {
  tropical_depression: '#5ebaff',
  tropical_storm: '#00c5a3',
  cat_1: '#ffe066',
  cat_2: '#ffb347',
  cat_3: '#ff7f2a',
  cat_4: '#e8382e',
  cat_5: '#b0167e',
}

export const RISK_BANDS: RiskBand[] = ['low', 'moderate', 'high', 'severe']

export const RISK_BAND_LABEL: Record<RiskBand, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
}

export const RISK_BAND_COLOR: Record<RiskBand, string> = {
  low: '#3b9a57',
  moderate: '#e0b100',
  high: '#e46c0a',
  severe: '#c0262d',
}
