import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api } from '../lib/api'
import type { RecentItem, WishlistInput, WishlistItem } from '../lib/api'

interface LibraryContextValue {
  wishlist: WishlistItem[]
  recents: RecentItem[]
  error: string | null
  wishlisted: (url: string) => WishlistItem | undefined
  toggleWishlist: (item: WishlistInput) => Promise<void>
  removeFromWishlist: (id: number) => Promise<void>
  removeRecent: (id: string) => Promise<void>
  refreshRecents: () => Promise<void>
}

const LibraryContext = createContext<LibraryContextValue | null>(null)

/** The shopper's wishlist and recently searched items, shared across pages. */
export function LibraryProvider({ children }: { children: ReactNode }) {
  const [wishlist, setWishlist] = useState<WishlistItem[]>([])
  const [recents, setRecents] = useState<RecentItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [nextWishlist, nextRecents] = await Promise.all([api.wishlist(), api.recentItems()])
      setWishlist(nextWishlist)
      setRecents(nextRecents)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    Promise.all([api.wishlist(), api.recentItems()])
      .then(([nextWishlist, nextRecents]) => {
        setWishlist(nextWishlist)
        setRecents(nextRecents)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  const value = useMemo<LibraryContextValue>(
    () => ({
      wishlist,
      recents,
      error,
      wishlisted: (url) => wishlist.find((w) => w.url === url),
      // Wishlist changes update local state from the API response, so hearts respond at once.
      toggleWishlist: async (item) => {
        const existing = wishlist.find((w) => w.url === item.url)
        if (existing) {
          await api.removeFromWishlist(existing.id)
          setWishlist((current) => current.filter((w) => w.id !== existing.id))
        } else {
          const saved = await api.addToWishlist(item)
          setWishlist((current) => [saved, ...current.filter((w) => w.id !== saved.id)])
        }
      },
      removeFromWishlist: async (id) => {
        await api.removeFromWishlist(id)
        setWishlist((current) => current.filter((w) => w.id !== id))
      },
      removeRecent: async (id) => {
        await api.removeRecent(id)
        await load()
      },
      refreshRecents: load,
    }),
    [wishlist, recents, error, load],
  )

  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary(): LibraryContextValue {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary must be used inside LibraryProvider')
  return context
}
