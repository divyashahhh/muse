import { useCallback, useEffect, useState } from 'react'

export type RequestState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: string }
  | { status: 'success'; data: T }

/**
 * Run `request(false)` on mount; `reload()` re-runs it with `refresh = true`.
 * Mount the owning component with a `key` so a new resource starts fresh.
 */
export function useRequest<T>(request: (refresh: boolean) => Promise<T>) {
  const [state, setState] = useState<RequestState<T>>({ status: 'loading' })

  const settle = useCallback((promise: Promise<T>) => {
    let cancelled = false
    promise
      .then((data) => !cancelled && setState({ status: 'success', data }))
      .catch((e: Error) => !cancelled && setState({ status: 'error', error: e.message }))
    return () => {
      cancelled = true
    }
  }, [])

  // `request` is intentionally read once per mount; callers key the component instead.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => settle(request(false)), [settle])

  const reload = () => {
    setState({ status: 'loading' })
    settle(request(true))
  }

  return [state, reload] as const
}
