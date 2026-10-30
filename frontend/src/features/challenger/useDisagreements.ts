import { useCallback } from 'react'
import { getDisagreements } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'

/** The disagreements at an advisory; nothing to load before advisory 1. */
export function useDisagreements(advisoryNo: number) {
  const loader = useCallback(() => getDisagreements(advisoryNo), [advisoryNo])
  return useLoad(advisoryNo > 0 ? loader : null)
}
