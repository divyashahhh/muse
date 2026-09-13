import { useState } from 'react'

import type { SavedItemInput, SavedListName } from '../lib/api'
import { useSaved } from '../saved/SavedContext'

interface SaveButtonsProps {
  item: Omit<SavedItemInput, 'list'>
  compact?: boolean
}

const LABELS: Record<SavedListName, { add: string; added: string }> = {
  bag: { add: 'Add to bag', added: 'In bag' },
  wishlist: { add: '♡ Wishlist', added: '♥ Wishlisted' },
}

export function SaveButtons({ item, compact = false }: SaveButtonsProps) {
  const saved = useSaved()
  const [busy, setBusy] = useState<SavedListName | null>(null)

  async function toggle(list: SavedListName) {
    setBusy(list)
    try {
      const existing = saved.find(item.url, list)
      if (existing) await saved.remove(existing.id)
      else await saved.save({ ...item, list })
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className={`flex gap-2 ${compact ? '' : 'mt-3'}`}>
      {(['bag', 'wishlist'] as const).map((list) => {
        const isSaved = Boolean(saved.find(item.url, list))
        return (
          <button
            key={list}
            type="button"
            disabled={busy !== null}
            onClick={() => toggle(list)}
            aria-pressed={isSaved}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition disabled:opacity-50 ${
              isSaved ? 'border-ink bg-ink text-paper' : 'border-line bg-card hover:border-ink'
            }`}
          >
            {isSaved ? LABELS[list].added : LABELS[list].add}
          </button>
        )
      })}
    </div>
  )
}
