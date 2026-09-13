import { useEffect, useState } from 'react'

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: Error }
  | { status: 'success'; data: T }

type Fetcher<T> = (signal: AbortSignal) => Promise<T>

/**
 * Run an API call on mount and whenever `fetcher` changes, aborting stale requests.
 * Pass a stable function (a module-level call or one wrapped in useCallback).
 */
export function useApi<T>(fetcher: Fetcher<T>): AsyncState<T> {
  // Results are tagged with the fetcher that produced them, so a changed fetcher
  // reads as loading without a synchronous reset inside the effect.
  const [settled, setSettled] = useState<{ fetcher: Fetcher<T>; state: AsyncState<T> } | null>(
    null,
  )

  useEffect(() => {
    const controller = new AbortController()
    fetcher(controller.signal)
      .then((data) => setSettled({ fetcher, state: { status: 'success', data } }))
      .catch((error: Error) => {
        if (!controller.signal.aborted) setSettled({ fetcher, state: { status: 'error', error } })
      })
    return () => controller.abort()
  }, [fetcher])

  return settled?.fetcher === fetcher ? settled.state : { status: 'loading' }
}
