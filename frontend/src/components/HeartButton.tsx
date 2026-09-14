import { useState } from 'react'

import type { WishlistInput } from '../lib/api'
import { useLibrary } from '../library/LibraryContext'
import { HeartIcon } from './Icons'

interface HeartButtonProps {
  item: WishlistInput
  variant?: 'floating' | 'outline'
}

export function HeartButton({ item, variant = 'floating' }: HeartButtonProps) {
  const library = useLibrary()
  const [busy, setBusy] = useState(false)
  const saved = Boolean(library.wishlisted(item.url))

  async function toggle() {
    setBusy(true)
    try {
      await library.toggleWishlist(item)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const styles =
    variant === 'floating'
      ? 'size-9 bg-white shadow-sm hover:scale-105'
      : 'size-12 border border-line bg-white hover:border-brown'

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={saved}
      aria-label={saved ? 'Remove from wishlist' : 'Add to wishlist'}
      className={`flex shrink-0 items-center justify-center rounded-full transition disabled:opacity-60 ${styles} ${
        saved ? 'text-red-500' : 'text-ink'
      }`}
    >
      <HeartIcon filled={saved} size={variant === 'floating' ? 18 : 20} />
    </button>
  )
}
