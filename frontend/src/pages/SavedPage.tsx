import { Link, useSearchParams } from 'react-router'

import type { SavedListName } from '../lib/api'
import { formatPrice, hostname } from '../lib/format'
import { useSaved } from '../saved/SavedContext'

const TITLES: Record<SavedListName, string> = { bag: 'Shopping bag', wishlist: 'Wishlist' }

export function SavedPage() {
  const [params, setParams] = useSearchParams()
  const list: SavedListName = params.get('list') === 'wishlist' ? 'wishlist' : 'bag'
  const other: SavedListName = list === 'bag' ? 'wishlist' : 'bag'
  const saved = useSaved()
  const items = saved.items.filter((s) => s.list === list)

  // Totals per currency: search results can mix currencies.
  const totals = new Map<string, number>()
  for (const s of items) {
    if (s.price !== null) totals.set(s.currency ?? '', (totals.get(s.currency ?? '') ?? 0) + s.price)
  }

  return (
    <div>
      <div className="flex gap-6 border-b border-line">
        {(['bag', 'wishlist'] as const).map((name) => (
          <button
            key={name}
            onClick={() => setParams({ list: name })}
            className={`-mb-px border-b-2 pb-3 font-display text-2xl ${
              list === name ? 'border-ink' : 'border-transparent text-muted'
            }`}
          >
            {TITLES[name]}{' '}
            <span className="font-sans text-sm">({saved.items.filter((s) => s.list === name).length})</span>
          </button>
        ))}
      </div>

      {saved.error && <p className="mt-6 text-sm text-red-700">{saved.error}</p>}

      {items.length === 0 ? (
        <p className="mt-8 text-muted">
          Nothing here yet. <Link to="/" className="underline">Search for an item</Link> to start saving.
        </p>
      ) : (
        <>
          <ul className="mt-6 divide-y divide-line rounded-xl border border-line bg-card">
            {items.map((s) => (
              <li key={s.id} className="flex gap-4 p-4">
                <div className="size-20 shrink-0 overflow-hidden rounded-lg bg-white">
                  {s.image_url && (
                    <img src={s.image_url} alt="" className="h-full w-full object-contain" referrerPolicy="no-referrer" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted">{s.retailer ?? hostname(s.url)}</p>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 hover:underline">
                    {s.title}
                  </a>
                  <p className="mt-1 font-semibold">{formatPrice(s.price, s.currency)}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2 text-xs">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-full bg-ink px-3 py-1.5 font-medium text-paper"
                  >
                    Buy at retailer
                  </a>
                  <button type="button" onClick={() => saved.move(s.id, other)} className="underline">
                    Move to {TITLES[other].toLowerCase()}
                  </button>
                  <button type="button" onClick={() => saved.remove(s.id)} className="text-muted underline">
                    Remove
                  </button>
                  {s.item_id && (
                    <Link to={`/items/${s.item_id}`} className="text-muted underline">
                      Compare prices
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {list === 'bag' && totals.size > 0 && (
            <p className="mt-4 text-right">
              Estimated total:{' '}
              <span className="font-semibold">
                {[...totals].map(([currency, sum]) => formatPrice(sum, currency || null)).join(' + ')}
              </span>
              <span className="block text-xs text-muted">
                Checkout happens on each retailer&rsquo;s site. Muse doesn&rsquo;t sell items directly.
              </span>
            </p>
          )}
        </>
      )}
    </div>
  )
}
