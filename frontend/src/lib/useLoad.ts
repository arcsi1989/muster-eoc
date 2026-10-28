import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../api/client'

export type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ok'; data: T }

type Outcome<T> = Extract<LoadState<T>, { status: 'error' | 'ok' }>

export function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'network', 'Could not reach the backend')
}

/**
 * Loads data with explicit states (CODING_STANDARDS F3). A null loader means "nothing to load".
 * Loading is derived during render: an outcome only counts for the loader and attempt it came from.
 */
export function useLoad<T>(loader: (() => Promise<T>) | null) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ loader: () => Promise<T>; attempt: number; outcome: Outcome<T> } | null>(
    null,
  )

  useEffect(() => {
    if (!loader) return
    let cancelled = false
    loader().then(
      (data) => !cancelled && setResult({ loader, attempt, outcome: { status: 'ok', data } }),
      (e: unknown) => !cancelled && setResult({ loader, attempt, outcome: { status: 'error', error: toApiError(e) } }),
    )
    return () => {
      cancelled = true
    }
  }, [loader, attempt])

  const state: LoadState<T> = !loader
    ? { status: 'idle' }
    : result && result.loader === loader && result.attempt === attempt
      ? result.outcome
      : { status: 'loading' }

  const retry = useCallback(() => setAttempt((a) => a + 1), [])
  /** Replaces the data with a fresher copy (for example the response of an action). */
  const setData = useCallback(
    (data: T) => loader && setResult({ loader, attempt, outcome: { status: 'ok', data } }),
    [loader, attempt],
  )

  return { state, retry, setData }
}
