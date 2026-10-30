import { useCallback } from 'react'
import { getTrace } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'

/** The run trace of an issued advisory; nothing to load before advisory 1. */
export function useRunTrace(advisoryNo: number) {
  const loader = useCallback(() => getTrace(advisoryNo), [advisoryNo])
  return useLoad(advisoryNo > 0 ? loader : null)
}
