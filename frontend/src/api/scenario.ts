import type { AdvisoryChanges, Asset, Coastline, RiskList, Scenario } from '../types/scenario'
import { api } from './client'

export const getScenario = () => api<Scenario>('/advisories')
export const nextAdvisory = () => api<Scenario>('/advisories/next', { method: 'POST' })
export const resetScenario = () => api<Scenario>('/advisories/reset', { method: 'POST' })
export const getAssets = () => api<Asset[]>('/assets')
export const getCoastline = () => api<Coastline>('/coastline')
export const getRisk = (advisoryNo: number) => api<RiskList>(`/risk?advisory=${advisoryNo}`)
export const getChanges = (advisoryNo: number) => api<AdvisoryChanges>(`/advisories/${advisoryNo}/changes`)
