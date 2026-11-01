import { useCallback } from 'react'
import { getForecast } from '../../api/scenario'
import { useLoad } from '../../lib/useLoad'

/** The outage forecast of an issued advisory; nothing to load before advisory 1. */
export function useForecast(advisoryNo: number) {
  const loader = useCallback(() => getForecast(advisoryNo), [advisoryNo])
  return useLoad(advisoryNo > 0 ? loader : null)
}
