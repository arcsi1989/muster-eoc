import type {
  AdvisoryChanges,
  Alert,
  AuditActor,
  AuditEvent,
  Calibration,
  ChatReply,
  ChatTurn,
  Clause,
  Asset,
  Coastline,
  DecisionAction,
  DecisionPackage,
  Declaration,
  Explanation,
  Exposure,
  Facility,
  Finding,
  LineageEntry,
  ModelVersion,
  RiskList,
  Role,
  Scenario,
  Sitrep,
  StagingArea,
} from '../types/scenario'
import { api } from './client'

export const getScenario = () => api<Scenario>('/advisories')
export const nextAdvisory = () => api<Scenario>('/advisories/next', { method: 'POST' })
export const resetScenario = () => api<Scenario>('/advisories/reset', { method: 'POST' })
export const getAssets = () => api<Asset[]>('/assets')
export const getCoastline = () => api<Coastline>('/coastline')
export const getRisk = (advisoryNo: number) => api<RiskList>(`/risk?advisory=${advisoryNo}`)
export const getChanges = (advisoryNo: number) => api<AdvisoryChanges>(`/advisories/${advisoryNo}/changes`)
export const getFacilities = () => api<Facility[]>('/facilities')
export const getStagingAreas = () => api<StagingArea[]>('/staging-areas')
/** Everything the maps draw that does not change with the advisory. */
export const getTerritory = async () => {
  const [assets, coastline, facilities, stagingAreas] = await Promise.all([
    getAssets(),
    getCoastline(),
    getFacilities(),
    getStagingAreas(),
  ])
  return { assets, coastline, facilities, stagingAreas }
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
export const getAudit = (actor?: AuditActor) =>
  api<AuditEvent[]>(actor ? `/audit?actor=${encodeURIComponent(actor)}` : '/audit')
export const postChat = (message: string, history: ChatTurn[]) =>
  api<ChatReply>('/copilot/chat', { method: 'POST', body: JSON.stringify({ message, history }) })
export const runCalibration = () => api<Calibration>('/calibration/run', { method: 'POST' })
export const getModelVersions = () => api<ModelVersion[]>('/model-versions')
export const approveModelVersion = (versionId: number, role: Role) =>
  api<ModelVersion>(`/model-versions/${versionId}/approve`, { method: 'POST', body: JSON.stringify({ role }) })
