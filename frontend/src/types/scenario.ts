// Mirrors the backend response models (backend app/api/schemas.py).

export type ActivationLevel = 'monitor' | 'prepare' | 'full'
export type AssetType = 'substation' | 'pump_station' | 'treatment_plant'

export interface Point {
  x_km: number
  y_km: number
}

export interface TrackPoint extends Point {
  t_hours: number
  vmax_mph: number
  rmax_km: number
}

export interface Advisory {
  advisory_no: number
  issued_at: string
  hours_to_landfall: number
  activation_level: ActivationLevel | null
  max_wind_mph: number
  peak_surge_m: number
  landfall: Point
  track: TrackPoint[]
}

/** One advisory in the replay schedule; its forecast stays hidden until issued. */
export interface TimelineSlot {
  advisory_no: number
  hours_to_landfall: number
  activation_level: ActivationLevel | null
  issued: boolean
}

export interface Scenario {
  total_advisories: number
  /** 0 before advisory 1 */
  current_advisory: number
  timeline: TimelineSlot[]
  /** issued advisories only */
  advisories: Advisory[]
}

export interface RankMove {
  asset_id: string
  from_rank: number
  to_rank: number
}

export interface AdvisoryChanges {
  advisory_no: number
  /** null at the first advisory: everything is initial */
  previous_advisory_no: number | null
  landfall_shift: { distance_km: number; direction: string } | null
  max_wind_change_mph: number | null
  peak_surge_change_m: number | null
  activation_level_from: ActivationLevel | null
  activation_level_to: ActivationLevel | null
  top10_entered: string[]
  top10_left: string[]
  /** biggest move first */
  rank_moves: RankMove[]
}

export interface Asset extends Point {
  id: string
  name: string
  type: AssetType
  customers_served: number
}

export interface Coastline {
  coastline: Point[]
  land: Point[]
}

export interface RiskItem {
  asset_id: string
  score: number
  rank: number
  /** null at the first advisory */
  previous_rank: number | null
}

export interface RiskList {
  advisory_no: number
  items: RiskItem[]
}
