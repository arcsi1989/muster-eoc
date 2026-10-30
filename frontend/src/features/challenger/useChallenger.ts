import { useCallback, useState } from 'react'
import type { ApiError } from '../../api/client'
import { approveModelVersion, getChallenger, proposeChallenger } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { ModelVersion, Role } from '../../types/scenario'

/** The challenger and its promotion: proposed only if the rule allows it, then approved by a person. */
export function useChallenger() {
  const challenger = useLoad(getChallenger)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<ApiError | null>(null)

  const { state, setData } = challenger
  const current = state.status === 'ok' ? state.data : null
  const act = useCallback(
    async (action: () => Promise<ModelVersion>) => {
      if (!current) return
      setBusy(true)
      setActionError(null)
      try {
        setData({ ...current, model_version: await action() })
      } catch (e) {
        setActionError(toApiError(e))
      } finally {
        setBusy(false)
      }
    },
    [current, setData],
  )

  const propose = useCallback(() => act(proposeChallenger), [act])
  const approve = useCallback(
    (role: Role) => current && act(() => approveModelVersion(current.model_version.id, role)),
    [act, current],
  )

  return { challenger, busy, actionError, propose, approve }
}
