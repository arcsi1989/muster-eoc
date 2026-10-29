import type {
  AdvisoryChanges,
  Alert,
  AuditActor,
  AuditEvent,
  ChatReply,
  ChatTurn,
  Clause,
  Asset,
  Coastline,
  DecisionAction,
  DecisionPackage,
  Explanation,
  Exposure,
  Facility,
  Finding,
  LineageEntry,
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
export const approveSitrep = (advisoryNo: number, role: Role, text: string) =>
  api<Sitrep>(`/sitrep/${advisoryNo}/approve`, { method: 'POST', body: JSON.stringify({ role, text }) })
export const getAudit = (actor?: AuditActor) =>
  api<AuditEvent[]>(actor ? `/audit?actor=${encodeURIComponent(actor)}` : '/audit')
export const postChat = (message: string, history: ChatTurn[]) =>
  api<ChatReply>('/copilot/chat', { method: 'POST', body: JSON.stringify({ message, history }) })
