import type {
  AdvisoryChanges,
  Alert,
  AuditActor,
  AuditEvent,
  Calibration,
  Challenger,
  ChatReply,
  ChatTurn,
  Clause,
  CopilotStep,
  Asset,
  Coastline,
  District,
  DecisionAction,
  DecisionPackage,
  Declaration,
  Disagreements,
  Explanation,
  Exposure,
  Facility,
  FieldOutcome,
  FieldReport,
  FieldTask,
  Finding,
  LineageEntry,
  ModelVersion,
  Planning,
  RiskList,
  Role,
  RunTrace,
  Scenario,
  Sitrep,
  StagingArea,
} from '../types/scenario'
import { ApiError, STREAMED_ERROR_STATUS, api, errorFrom, streamEvents } from './client'

export const getScenario = () => api<Scenario>('/advisories')
export const nextAdvisory = () => api<Scenario>('/advisories/next', { method: 'POST' })
export const resetScenario = () => api<Scenario>('/advisories/reset', { method: 'POST' })
export const getAssets = () => api<Asset[]>('/assets')
export const getCoastline = () => api<Coastline>('/coastline')
export const getDistricts = () => api<District[]>('/districts')
export const getRisk = (advisoryNo: number) => api<RiskList>(`/risk?advisory=${advisoryNo}`)
export const getChanges = (advisoryNo: number) => api<AdvisoryChanges>(`/advisories/${advisoryNo}/changes`)
export const getFacilities = () => api<Facility[]>('/facilities')
export const getStagingAreas = () => api<StagingArea[]>('/staging-areas')
/** Everything the maps draw that does not change with the advisory. */
export const getTerritory = async () => {
  const [assets, coastline, districts, facilities, stagingAreas] = await Promise.all([
    getAssets(),
    getCoastline(),
    getDistricts(),
    getFacilities(),
    getStagingAreas(),
  ])
  return { assets, coastline, districts, facilities, stagingAreas }
}
export const getLineage = () => api<LineageEntry[]>('/lineage')
export const getExposure = (advisoryNo: number) => api<Exposure[]>(`/exposure?advisory=${advisoryNo}`)
export const getExplanation = (assetId: string, advisoryNo: number) =>
  api<Explanation>(`/assets/${encodeURIComponent(assetId)}/explain?advisory=${advisoryNo}`)
export const getAlerts = (advisoryNo: number) => api<Alert[]>(`/alerts?advisory=${advisoryNo}`)
export const getFindings = (advisoryNo: number) => api<Finding[]>(`/findings?advisory=${advisoryNo}`)
export const getClauses = () => api<Clause[]>('/clauses')
export const getPackage = (advisoryNo: number) => api<DecisionPackage>(`/packages/${advisoryNo}`)
export const postDecision = (
  advisoryNo: number,
  itemId: number,
  decision: { role: Role; action: DecisionAction; reason?: string },
) =>
  api<DecisionPackage>(`/packages/${advisoryNo}/items/${itemId}/decision`, {
    method: 'POST',
    body: JSON.stringify(decision),
  })
/** Declares the level the current package proposes (P-2.5); returns the updated package. */
export const postDeclaration = (declaration: Declaration) =>
  api<DecisionPackage>('/activation/declare', { method: 'POST', body: JSON.stringify(declaration) })
export const approveSitrep = (advisoryNo: number, role: Role, text: string) =>
  api<Sitrep>(`/sitrep/${advisoryNo}/approve`, { method: 'POST', body: JSON.stringify({ role, text }) })
/** The planning draft of the period after the advisory; null while none is drafted. */
export const getPlanning = (advisoryNo: number) =>
  api<Planning>(`/packages/${advisoryNo}/planning`).catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  })
export const draftPlanning = (advisoryNo: number) =>
  api<Planning>(`/packages/${advisoryNo}/planning/draft`, { method: 'POST' })
/** The next release approval: the Planning Section Chief, then the role that commands. */
export const releasePlanning = (advisoryNo: number, role: Role) =>
  api<Planning>(`/packages/${advisoryNo}/planning/release`, { method: 'POST', body: JSON.stringify({ role }) })
export const getAudit = (actor?: AuditActor) =>
  api<AuditEvent[]>(actor ? `/audit?actor=${encodeURIComponent(actor)}` : '/audit')
/** Asks the copilot and reports each step as it happens; resolves with the validated answer. */
export async function streamChat(
  message: string,
  history: ChatTurn[],
  onStep: (step: CopilotStep) => void,
): Promise<ChatReply> {
  let reply: ChatReply | null = null
  let failed: ApiError | null = null
  await streamEvents('/copilot/chat/stream', { message, history }, ({ event, data }) => {
    if (event === 'step') onStep(data as CopilotStep)
    else if (event === 'answer') reply = data as ChatReply
    else if (event === 'error') failed = errorFrom(data, STREAMED_ERROR_STATUS, 'The copilot could not answer')
  })
  if (failed) throw failed
  if (!reply) throw new ApiError(STREAMED_ERROR_STATUS, 'stream_failed', 'The answer did not arrive')
  return reply
}
export const runCalibration = () => api<Calibration>('/calibration/run', { method: 'POST' })
export const getModelVersions = () => api<ModelVersion[]>('/model-versions')
export const approveModelVersion = (versionId: number, role: Role) =>
  api<ModelVersion>(`/model-versions/${versionId}/approve`, { method: 'POST', body: JSON.stringify({ role }) })
/** The challenger and both models on the held-out storm; null when no challenger is loaded. */
export const getChallenger = () =>
  api<Challenger>('/challenger').catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  })
export const proposeChallenger = () => api<ModelVersion>('/challenger/propose', { method: 'POST' })
export const getDisagreements = (advisoryNo: number) =>
  api<Disagreements>(`/challenger/disagreements?advisory=${advisoryNo}`)
export const getFieldDistrictNames = () => api<string[]>('/field/districts')
export const getFieldTasks = (district: string) =>
  api<FieldTask[]>(`/field/tasks?district=${encodeURIComponent(district)}`)
/** Reports a field task done or blocked; returns the district's tasks as they now stand. */
export const postFieldReport = (itemId: number, outcome: FieldOutcome, report: FieldReport) =>
  api<FieldTask[]>(`/field/tasks/${itemId}/${outcome}`, { method: 'POST', body: JSON.stringify(report) })
/** What the agent did for an issued advisory: its cycle nodes and generations as spans. */
export const getTrace = (advisoryNo: number) => api<RunTrace>(`/advisories/${advisoryNo}/trace`)
