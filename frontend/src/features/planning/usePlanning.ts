import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import { draftPlanning, getPackage, getPlanning, releasePlanning } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { Planning, Role } from '../../types/scenario'

/** Errors that mean the draft or package on screen is stale: reload both. */
const STALE = new Set(['package_closed', 'planning_released', 'planning_in_release'])

/** The planning draft of the period after the advisory, its package (who commands, is it open),
 * and the Planning Section Chief's drafting and the two release approvals. */
export function usePlanning(advisoryNo: number) {
  const planningLoader = useCallback(() => getPlanning(advisoryNo), [advisoryNo])
  const packageLoader = useCallback(() => getPackage(advisoryNo), [advisoryNo])
  const planning = useLoad<Planning | null>(advisoryNo > 0 ? planningLoader : null)
  const pkg = useLoad(advisoryNo > 0 ? packageLoader : null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<ApiError | null>(null)

  const { setData, retry: reloadPlanning } = planning
  const { retry: reloadPackage } = pkg
  const send = useCallback(
    async (action: () => Promise<Planning>) => {
      setBusy(true)
      setActionError(null)
      try {
        setData(await action())
      } catch (e) {
        const apiError = toApiError(e)
        setActionError(apiError)
        if (STALE.has(apiError.code)) {
          reloadPlanning()
          reloadPackage()
        }
      } finally {
        setBusy(false)
      }
    },
    [setData, reloadPlanning, reloadPackage],
  )

  return {
    planning,
    pkg,
    busy,
    actionError,
    draft: () => send(() => draftPlanning(advisoryNo)),
    release: (role: Role) => send(() => releasePlanning(advisoryNo, role)),
  }
}
