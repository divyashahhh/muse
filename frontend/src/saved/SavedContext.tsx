import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api } from '../lib/api'
import type { SavedItem, SavedItemInput, SavedListName } from '../lib/api'

interface SavedContextValue {
  items: SavedItem[]
  error: string | null
  find: (url: string, list: SavedListName) => SavedItem | undefined
  save: (item: SavedItemInput) => Promise<void>
  move: (id: number, list: SavedListName) => Promise<void>
  remove: (id: number) => Promise<void>
}

const SavedContext = createContext<SavedContextValue | null>(null)

export function SavedProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<SavedItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setItems(await api.listSaved())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    api
      .listSaved()
      .then(setItems)
      .catch((e: Error) => setError(e.message))
  }, [])

  const value = useMemo<SavedContextValue>(
    () => ({
      items,
      error,
      find: (url, list) => items.find((s) => s.url === url && s.list === list),
      save: async (item) => {
        await api.save(item)
        await refresh()
      },
      move: async (id, list) => {
        await api.moveSaved(id, list)
        await refresh()
      },
      remove: async (id) => {
        await api.removeSaved(id)
        await refresh()
      },
    }),
    [items, error, refresh],
  )

  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSaved(): SavedContextValue {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSaved must be used inside SavedProvider')
  return context
}
