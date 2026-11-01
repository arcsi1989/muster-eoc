// Mirrors the backend API response models (backend muster/api/schemas.py), field for field.

export type ActivationLevel = 'monitor' | 'prepare' | 'full'
export type AssetType = 'substation' | 'pump_station' | 'treatment_plant'
export type FacilityType = 'hospital' | 'shelter'

export interface Point {
  x_km: number
  y_km: number
}

/** Saffir-Simpson category from the 1-minute sustained wind (config/scoring.yaml) */
export type IntensityCategory =
  | 'tropical_depression'
  | 'tropical_storm'
  | 'cat_1'
  | 'cat_2'
  | 'cat_3'
  | 'cat_4'
  | 'cat_5'

/** Where the storm is (or is forecast to be) at a time, with its intensity. */
export interface StormPosition extends Point {
  valid_at: string
  vmax_mph: number
  category: IntensityCategory
}

export interface TrackPoint extends StormPosition {
  /** lead time: valid_at is the issue time + t_hours */
  t_hours: number
  rmax_km: number
}

/** Where the storm was when an earlier advisory was issued. */
export interface PastPosition extends StormPosition {
  advisory_no: number
}

export interface Advisory {
  advisory_no: number
  issued_at: string
  hours_to_landfall: number
  activation_level: ActivationLevel | null
  max_wind_mph: number
  peak_surge_m: number
  landfall: Point
  /** forecast points */
  track: TrackPoint[]
  /** earlier advisories, oldest first */
  past_positions: PastPosition[]
  /** outline of the NHC-style forecast cone */
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

/** A fictional district a field supervisor works, west to east across the territory. */
export interface District {
  name: string
  west_km: number
  east_km: number
  /** where the maps write its name */
  label: Point
  /** where it meets its western neighbour; empty for the westernmost */
  boundary: Point[]
}

export type Confidence = 'high' | 'medium' | 'low'

/** Storm map colour, from p_fail (config/scoring.yaml) */
export type RiskBand = 'low' | 'moderate' | 'high' | 'severe'
export type TopFactor = 'wind' | 'flood'

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
  risk_band: RiskBand
  /** the hazard with the higher p_fail on its own */
  top_factor: TopFactor
}

export interface RiskList {
  advisory_no: number
  model_version: number // the fragility curves that scored the advisory
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
  /** null when no challenger scored the asset in shadow */
  challenger: ChallengerView | null
}

/** One of the challenger's features for an asset (backend ChallengerFeatureOut). */
export interface ChallengerFeature {
  feature: string
  /** the asset type is a category */
  value: number | string
  /** p_fail minus p_fail with this feature alone at the training baseline */
  contribution: number
}

/** The challenger's shadow score of an asset at an advisory (backend ChallengerViewOut). */
export interface ChallengerView {
  model_version: number
  rank: number
  p_fail: number
  /** the largest contributions first */
  top_features: ChallengerFeature[]
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

/** The role that commands: the Incident Commander at Full activation, the Director below it (P-2.3) */
export type Commander = 'incident_commander' | 'director'
export type Role = Commander | 'planning' | 'operations' | 'logistics' | 'regulatory_liaison'
export interface Declaration {
  level: ActivationLevel
  declared_by: Role
  reason?: string
}

export type DecisionAction = 'approve' | 'override' | 'defer' | 'alternative'
export type ItemStatus = 'pending' | 'approved' | 'overridden' | 'deferred' | 'alternative' | 'not_decided'

/** One gap with its proposed action, or one conflict, awaiting a person's decision. */
export interface PackageItem {
  id: number
  rule_id: string
  title: string
  entity_id: string
  entity_name: string | null
  /** a proposal is the P-2.5 activation proposal: only a declaration closes it */
  kind: 'gap' | 'conflict' | 'proposal'
  proposed_action: string
  owner_role: string
  severity: string
  cites: string[]
  overdue: boolean
  status: ItemStatus
  decided_by: string | null
  reason: string | null
  decided_at: string | null
  /** the same work, approved in an earlier package, was reported blocked in the field */
  blocked_note: string | null
}

export interface DraftParagraph {
  text: string
  clause_ids: string[]
  asset_ids: string[]
}

export interface Draft {
  status: 'DRAFT'
  /** the provider that wrote it, or "template (fallback)" */
  provider: string
  /** the template draft replaced the provider's draft */
  fallback: boolean
  model: string | null
  /** null for template drafts: no prompt is used */
  prompt_version: string | null
  fallback_reason: string | null
  sections: { heading: string; paragraphs: DraftParagraph[] }[]
}

export interface Sitrep {
  advisory_no: number
  approved_text: string
  approved_by: string
  approved_at: string
  edited: boolean
}

export interface DecisionPackage {
  advisory_no: number
  status: 'open' | 'closed'
  /** the last declared level (P-2.5) */
  activation_level: ActivationLevel | null
  /** the level the playbook's time thresholds propose */
  proposed_activation_level: ActivationLevel | null
  decides_as_commander: Commander
  changes: AdvisoryChanges
  items: PackageItem[]
  draft: Draft | null
  /** the draft as editable plain text */
  draft_text: string | null
  sitrep: Sitrep | null
}

export type AuditActor = 'system' | 'agent' | 'human' | 'field_supervisor'

export interface AuditEvent {
  id: number
  /** wall-clock time */
  recorded_at: string
  /** scenario time: the advisory in force */
  advisory_no: number | null
  hours_to_landfall: number | null
  actor: AuditActor
  type: string
  summary: string
  payload: Record<string, unknown>
  input_hash: string
  versions: Record<string, unknown>
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatReply {
  answer: string
  /** only IDs a tool returned while answering */
  citations: { id: string; kind: 'asset' | 'clause' }[]
  /** the provider that answered, or "template (fallback)" */
  provider: string
  fallback: boolean
  tools_used: string[]
  /** the advisory the answer is about: the current one; null before advisory 1 */
  advisory: number | null
  work: CopilotWork
}

export interface CopilotToolCall {
  name: string
  args: Record<string, unknown>
  /** as the model was shown it: restricted fields already filtered */
  result: Record<string, unknown>
}

export interface CopilotAttempt {
  provider: string
  model: string | null
  prompt_version: string | null
  latency_ms: number
  input_tokens: number
  output_tokens: number
  /** what the validator found; empty when it passed */
  problems: string[]
  /** the provider failed; no result was validated */
  error: string | null
}

/** How the copilot got its answer: the "How I got this" panel. */
export interface CopilotWork {
  tool_calls: CopilotToolCall[]
  attempts: CopilotAttempt[]
  retries: number
  /** the answer passed the validator; false when the template replaced it */
  validated: boolean
  provider: string
  model: string | null
  prompt_version: string | null
  input_tokens: number
  output_tokens: number
  /** null: tokens from a model with no price in config/llm.yaml */
  cost_usd: number | null
  fallback: boolean
  fallback_reason: string | null
}

/** One step of a copilot turn as it happens; never answer text. */
export interface CopilotStep {
  kind: 'attempt' | 'validating' | 'validated' | 'rejected' | 'failed' | 'fallback' | 'tool_call'
  attempt: number
  provider: string
  problems: string[]
  reason: string | null
  tool: string | null
  args: Record<string, unknown>
}

export interface Curve {
  asset_type: string
  hazard: 'wind' | 'flood'
  /** median capacity: mph for wind, m for flood */
  theta: number
  beta: number
}

export interface ReliabilityBin {
  lower: number
  upper: number
  count: number
  /** null for an empty bin */
  mean_predicted: number | null
  observed_rate: number | null
}

export interface Backtest {
  model_version: number
  assets: number
  failures: number
  brier: number
  /** of assets, by predicted probability (0.10: the top decile) */
  top_fraction: number
  /** share of all failures among them */
  top_capture: number
  reliability: ReliabilityBin[]
}

export interface ModelVersion {
  id: number
  label: string
  /** fragility curves, or the challenger model (CR-03 C2) */
  kind: 'curves' | 'challenger'
  /** a challenger starts in shadow: it scores every advisory but ranks nothing */
  status: 'shadow' | 'proposed' | 'approved'
  /** the champion (the latest approved): ranks the next advisory */
  in_use: boolean
  /** empty for the challenger */
  curves: Curve[]
  created_at: string
  approved_by: string | null
  approved_at: string | null
}

export interface Calibration {
  storm: string
  /** the version in use */
  before: Backtest
  /** the proposed version */
  after: Backtest
  model_version: ModelVersion
}

/** A model's metrics on the held-out storm (backend ModelMetricsOut). */
export interface ModelMetrics {
  assets: number
  failures: number
  brier: number
  /** null when every asset had the same outcome */
  roc_auc: number | null
  top_fraction: number
  top_capture: number
  reliability: ReliabilityBin[]
}

export interface PromotionCriterion {
  name: 'brier_improvement' | 'top_capture_gain' | 'calibration_error'
  /** the challenger's margin over the champion, or its calibration error */
  value: number
  /** config/models.yaml promotion */
  threshold: number
  passed: boolean
}

export interface PromotionCheck {
  /** the held-out storm the rule is checked on */
  storm: string
  /** the challenger may be proposed */
  passed: boolean
  criteria: PromotionCriterion[]
}

/** GET /challenger (backend ChallengerOut). */
export interface Challenger {
  model_version: ModelVersion
  /** on the held-out storm */
  challenger: ModelMetrics
  /** the published curves on the same storm */
  champion: ModelMetrics
  promotion: PromotionCheck
}

/** An asset the challenger ranks in its top N that the champion does not (backend DisagreementOut). */
export interface Disagreement {
  asset_id: string
  asset_name: string
  challenger_rank: number
  champion_rank: number
  challenger_p_fail: number
  champion_p_fail: number
  /** why the challenger ranks it higher */
  top_features: ChallengerFeature[]
}

/** GET /challenger/disagreements (backend DisagreementsOut). */
export interface Disagreements {
  advisory_no: number
  /** the challenger's model version */
  model_version: number
  top_n: number
  /** by the challenger's rank; empty when it is the champion */
  items: Disagreement[]
}

export type FieldTaskStatus = 'open' | 'done' | 'blocked'
/** what a field supervisor reports */
export type FieldOutcome = Exclude<FieldTaskStatus, 'open'>

/** The request body of a report (backend FieldReportIn). */
export interface FieldReport {
  /** the supervisor's own district */
  district: string
  note?: string
}

/** An approved item that needs field work, as a field supervisor sees it. */
export interface FieldTask {
  item_id: number
  /** the advisory whose package approved it */
  approved_in: number
  rule_id: string
  /** the clause's title, one line */
  why: string
  action: string
  entity_id: string
  entity_name: string | null
  approved_by: string | null
  approved_at: string | null
  /** prohibitions in force at the site now (P-4.7); Done is refused */
  stop_work: string[]
  status: FieldTaskStatus
  note: string | null
  reported_at: string | null
}

/** One work assignment of the ICS-215: an approved field task and the resource it needs */
export interface Ics215Row {
  /** the approved package item */
  item_id: number
  clause_id: string
  location_id: string
  location: string
  work_assignment: string
  resource_kind: string
  required: number
  have: number
  /** required minus have */
  need: number
  /** the nearest usable staging area; null if none is usable */
  reporting_location_id: string | null
  reporting_location: string | null
  /** scenario time, hours to landfall: the next period's start */
  requested_arrival_hours: number
  /** prohibitions in force at the site now (P-4.7) */
  stop_work: string[]
}

/** One incident objective of the IAP draft; the citations come from the findings, never a model */
export interface IapObjective {
  text: string
  clause_ids: string[]
  entity_ids: string[]
}

/** The ICS-215 and IAP objectives drafted for the period after an advisory, DRAFT until the
 * Planning Section Chief approves and the commanding role releases them */
export interface Planning {
  /** the next operational period, in hours to landfall */
  period_start_hours: number
  period_end_hours: number
  ics215: Ics215Row[]
  objectives: IapObjective[]
  /** the provider that worded the objectives, or "template (fallback)" */
  provider: string
  fallback: boolean
  model: string | null
  /** null for the template wording */
  prompt_version: string | null
  fallback_reason: string | null
  advisory_no: number
  status: 'DRAFT' | 'released'
  drafted_at: string
  planning_approved_at: string | null
  /** the commanding role */
  released_by: string | null
  released_at: string | null
}

/** One span of the run trace: an advisory-cycle node or a grounded generation */
export interface TraceSpan {
  span_id: string
  /** a generation's node, or a span not stored (the HTTP request) */
  parent_span_id: string | null
  advisory_no: number | null
  kind: 'cycle_node' | 'generation'
  /** the cycle node, or the generation task (sitrep_draft, copilot, iap_objectives) */
  node: string
  started_at: string
  ended_at: string
  duration_ms: number
  /** paused: await_approval waiting for decisions */
  status: 'ok' | 'error' | 'paused'
  /** the provider that produced the result, or "template (fallback)" */
  provider: string | null
  model: string | null
  tokens_in: number
  tokens_out: number
  /** null: tokens from a model with no price in config/llm.yaml */
  cost_usd: number | null
  retries: number
  fallback: boolean
  fallback_reason: string | null
  /** generations only */
  validation: 'passed' | 'failed' | 'error' | null
  attempts: Record<string, unknown>[]
}

export interface TraceTotals {
  /** top-level spans: a generation is inside its node's time */
  latency_ms: number
  tokens_in: number
  tokens_out: number
  cost_usd: number
  unpriced_spans: number
  retries: number
  fallbacks: number
}

/** What the agent did for an advisory, with totals for the advisory and the demo run */
export interface RunTrace {
  /** the demo run since the backend started or the scenario was reset */
  run_id: string
  advisory_no: number
  spans: TraceSpan[]
  advisory_totals: TraceTotals
  run_totals: TraceTotals
}
