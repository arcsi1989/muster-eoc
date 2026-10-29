// Mirrors the backend API response models (backend app/api/schemas.py), field for field.

export type ActivationLevel = 'monitor' | 'prepare' | 'full'
export type AssetType = 'substation' | 'pump_station' | 'treatment_plant'
export type FacilityType = 'hospital' | 'shelter'

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
  /** outline of the forecast cone */
  cone: Point[]
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
  /** null for a few assets on purpose: imputed later, lowers confidence */
  elevation_m: number | null
  distance_to_coast_km: number
  install_year: number
  /** 1 good ... 5 very poor */
  condition_score: number
  last_inspection_date: string
  customers_served: number
}

export interface Facility extends Point {
  id: string
  name: string
  type: FacilityType
}

export interface StagingArea extends Point {
  id: string
  name: string
  elevation_m: number
  distance_to_coast_km: number
}

export interface QualityIssue {
  row: number
  record_id: string | null
  reason: string
}

export interface LineageEntry {
  file: string
  sha256: string
  loaded_at: string
  rows_ok: number
  rows_rejected: number
  issues: QualityIssue[]
}

export interface Coastline {
  coastline: Point[]
  land: Point[]
}

export type Confidence = 'high' | 'medium' | 'low'

export interface RiskItem {
  asset_id: string
  p_fail: number
  /** customer-equivalents */
  consequence: number
  /** p_fail x consequence */
  risk: number
  rank: number
  /** null at the first advisory */
  previous_rank: number | null
  confidence: Confidence
}

export interface RiskList {
  advisory_no: number
  items: RiskItem[]
}

export interface Exposure {
  site_id: string
  site_kind: 'asset' | 'staging_area'
  wind_p50_mph: number
  wind_p90_mph: number
  flood_depth_p50_m: number
  flood_depth_p90_m: number
  /** median hours until tropical-storm-force wind; null if never */
  tsforce_arrival_h: number | null
  elevation_imputed: boolean
}

export interface HazardFactor {
  /** published median capacity: mph for wind, m for flood */
  theta: number
  theta_adjusted: number
  beta: number
  /** this hazard alone, mean over ensemble members */
  p_fail: number
}

export interface DownstreamAsset {
  id: string
  /** share counted for this asset: its customers divided by its feeders */
  customers: number
  feeders: number
}

export interface WeightedFacility {
  id: string
  type: string
  /** share counted for this asset: the policy weight divided by its feeders */
  weight: number
  feeders: number
}

export interface Consequence {
  own_customers: number
  downstream_assets: DownstreamAsset[]
  facilities: WeightedFacility[]
  total: number
}

export interface DependencyLink {
  id: string
  kind: 'asset' | 'facility'
  name: string
}

export interface Explanation {
  asset: Asset
  advisory_no: number
  rank: number
  risk: number
  p_fail: number
  p_wind: number
  p_flood: number
  wind: HazardFactor
  flood: HazardFactor
  exposure: Exposure
  consequence: Consequence
  confidence: Confidence
  confidence_reasons: string[]
  feeds: DependencyLink[]
  fed_by: DependencyLink[]
}

export interface Alert {
  asset_id: string
  kind: 'risk_threshold' | 'top_n_entry' | 'rank_jump'
  message: string
}

export type FindingStatus = 'open' | 'satisfied' | 'conflict'

/** The result of evaluating one playbook rule for one entity at one advisory. */
export interface Finding {
  rule_id: string
  title: string
  entity_id: string
  entity_kind: 'event' | 'asset' | 'staging_area'
  entity_name: string | null
  status: FindingStatus
  severity: string
  owner_role: string
  /** clause IDs: the rule's own, plus the prohibition and P-8.2 for a conflict */
  cites: string[]
  overdue: boolean
  /** the values the rule engine decided on */
  details: Record<string, unknown>
}

export interface Clause {
  id: string
  section: string
  title: string
  text: string
}
