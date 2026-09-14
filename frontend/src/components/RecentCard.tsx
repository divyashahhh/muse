import { Link } from 'react-router'

import type { RecentItem } from '../lib/api'
import { formatPrice, timeAgo } from '../lib/format'
import { wishlistInputForItem } from '../lib/wishlist'
import { HeartButton } from './HeartButton'
import { TrashIcon } from './Icons'

export function RecentCard({ item, onRemove }: { item: RecentItem; onRemove?: () => void }) {
  return (
    <article className="group flex flex-col">
      <div className="relative overflow-hidden rounded-2xl bg-sand">
        <Link to={`/items/${item.id}`} className="block aspect-[4/5]">
          <img
            src={item.image_url}
            alt={item.product_name}
            loading="lazy"
            className="h-full w-full object-contain p-4 mix-blend-multiply transition duration-300 group-hover:scale-105"
          />
        </Link>
        <span className="absolute top-3 left-3 rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-ink shadow-sm">
          {item.source === 'url' ? 'From link' : 'From photo'}
        </span>
        <div className="absolute top-3 right-3 flex flex-col gap-2">
          <HeartButton item={wishlistInputForItem(item)} />
          {onRemove && (
            <button
              type="button"
              onClick={onRemove}
              aria-label="Remove from recents"
              className="flex size-9 items-center justify-center rounded-full bg-white text-ink shadow-sm transition hover:text-red-600"
            >
              <TrashIcon size={17} />
            </button>
          )}
        </div>
      </div>
      <p className="mt-3 flex justify-between gap-2 text-xs text-muted">
        <span className="truncate capitalize">{item.category}</span>
        <span className="shrink-0">{timeAgo(item.created_at)}</span>
      </p>
      <Link to={`/items/${item.id}`} className="mt-1 line-clamp-2 text-[15px] leading-snug hover:text-brown">
        {item.title ?? item.product_name}
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
        {item.price !== null && (
          <span className="mr-1 text-sm font-semibold text-brown">{formatPrice(item.price, item.currency)}</span>
        )}
        {item.discovered_at && <span className="rounded-full bg-cream px-2 py-0.5 text-brown">Discovered</span>}
        {item.prices_checked_at && <span className="rounded-full bg-cream px-2 py-0.5 text-brown">Prices compared</span>}
      </div>
    </article>
  )
}
