import { useMemo } from 'react'
import { getClauses } from '../api/scenario'
import { useLoad } from './useLoad'

const loadClauses = () => getClauses()

/** The playbook's clauses, loaded once per component and indexed by clause ID. */
export function useClauses() {
  const { state, retry } = useLoad(loadClauses)
  const clauses = useMemo(() => new Map(state.status === 'ok' ? state.data.map((c) => [c.id, c]) : []), [state])
  return { state, retry, clauses }
}
