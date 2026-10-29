import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import { getScenario, nextAdvisory, resetScenario } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { Scenario } from '../../types/scenario'

export function useScenario() {
  const { state, retry, setData } = useLoad<Scenario>(getScenario)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<ApiError | null>(null)

  const run = useCallback(
    async (action: () => Promise<Scenario>) => {
      setBusy(true)
      setActionError(null)
      try {
        setData(await action())
      } catch (e) {
        setActionError(toApiError(e))
      } finally {
        setBusy(false)
      }
    },
    [setData],
  )

  return {
    state,
    retry,
    busy,
    actionError,
    next: () => run(nextAdvisory),
    reset: () => run(resetScenario),
    /** reloads after a change made elsewhere, such as a declared activation level */
    refresh: () => run(getScenario),
  }
}
