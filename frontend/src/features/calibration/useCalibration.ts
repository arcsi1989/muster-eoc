import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import { approveModelVersion, getModelVersions, runCalibration } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { Calibration, Role } from '../../types/scenario'

/** The model versions, the back-test a person starts, and their approval of the proposed version. */
export function useCalibration() {
  const versions = useLoad(getModelVersions)
  // No loader until the person runs the back-test: the run stores a proposed version.
  const [runLoader, setRunLoader] = useState<(() => Promise<Calibration>) | null>(null)
  const result = useLoad<Calibration>(runLoader)
  const [approving, setApproving] = useState(false)
  const [approveError, setApproveError] = useState<ApiError | null>(null)

  const { retry: rerun, setData } = result
  const run = useCallback(() => {
    setApproveError(null)
    if (runLoader) rerun()
    else setRunLoader(() => runCalibration)
  }, [runLoader, rerun])

  const { retry: reloadVersions } = versions
  const approve = useCallback(
    async (calibration: Calibration, role: Role) => {
      setApproving(true)
      setApproveError(null)
      try {
        setData({ ...calibration, model_version: await approveModelVersion(calibration.model_version.id, role) })
        reloadVersions()
      } catch (e) {
        setApproveError(toApiError(e))
      } finally {
        setApproving(false)
      }
    },
    [setData, reloadVersions],
  )

  return { versions, result, run, approve, approving, approveError }
}
