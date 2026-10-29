import { ROLES, roleLabel } from '../../lib/roles'
import type { Role } from '../../types/scenario'

interface Props {
  role: Role
  onChange: (role: Role) => void
}

/** No login in the prototype: the operator says which role they decide as (decisions.md). */
export function RoleSelector({ role, onChange }: Props) {
  return (
    <label className="role-selector">
      Deciding as{' '}
      <select value={role} onChange={(e) => onChange(e.target.value as Role)}>
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {roleLabel(r)}
          </option>
        ))}
      </select>
    </label>
  )
}
