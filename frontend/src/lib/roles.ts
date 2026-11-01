import type { Role } from '../types/scenario'

const ROLE_LABEL: Record<Role, string> = {
  incident_commander: 'Incident Commander',
  director: 'Director',
  planning: 'Planning',
  operations: 'Operations',
  logistics: 'Logistics',
  regulatory_liaison: 'Regulatory Liaison',
}

export const ROLES = Object.keys(ROLE_LABEL) as Role[]

/** Owner roles come from the playbook rules as text; unknown ones show as they are. */
export const roleLabel = (role: string) => (role in ROLE_LABEL ? ROLE_LABEL[role as Role] : role)
