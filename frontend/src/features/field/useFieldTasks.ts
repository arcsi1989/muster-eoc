import { useCallback, useState } from 'react'
import type { ApiError } from '../../api/client'
import { getDistricts, getFieldTasks, postFieldReport } from '../../api/scenario'
import { toApiError, useLatestData, useLoad } from '../../lib/useLoad'
import type { FieldOutcome, FieldTask } from '../../types/scenario'

/** Refusals that mean the list on screen is stale: reload it. */
const STALE_TASKS = new Set(['stop_work', 'already_done', 'package_closed', 'not_found'])

/** The districts, the chosen district's field tasks, and a supervisor's reports on them. */
export function useFieldTasks() {
  const districts = useLoad(getDistricts)
  const [chosen, setChosen] = useState<string | null>(null)
  const district = chosen ?? (districts.state.status === 'ok' ? (districts.state.data[0] ?? null) : null)

  const loader = useCallback(() => getFieldTasks(district ?? ''), [district])
  const tasks = useLoad(district ? loader : null)
  /** kept while a reload runs, so the cards stay in place */
  const shown = useLatestData(tasks.state)
  const [error, setError] = useState<{ itemId: number; error: ApiError } | null>(null)
  const [busy, setBusy] = useState(false)

  const choose = useCallback((next: string) => {
    setChosen(next)
    setError(null)
  }, [])

  const { setData, retry } = tasks
  const report = useCallback(
    async (task: FieldTask, outcome: FieldOutcome, note?: string) => {
      if (!district) return
      setError(null)
      setBusy(true)
      try {
        setData(await postFieldReport(task.item_id, outcome, { district, note }))
      } catch (e) {
        const apiError = toApiError(e)
        setError({ itemId: task.item_id, error: apiError })
        if (STALE_TASKS.has(apiError.code)) retry()
      } finally {
        setBusy(false)
      }
    },
    [district, setData, retry],
  )

  return { districts, district, choose, tasks, shown, report, error, busy }
}
