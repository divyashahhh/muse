import type { Listing } from '../lib/api'
import { formatPrice, hostname } from '../lib/format'
import { SaveButtons } from './SaveButtons'

export function ListingCard({ listing, itemId }: { listing: Listing; itemId: string }) {
  const retailer = listing.retailer ?? hostname(listing.url)
  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-line bg-card">
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block aspect-square bg-white"
      >
        {listing.image_url ? (
          <img
            src={listing.image_url}
            alt={listing.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-full w-full object-contain p-2"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted">No image</div>
        )}
      </a>
      <div className="flex flex-1 flex-col p-3">
        <div className="flex items-center gap-1.5 text-xs text-muted">
          {listing.retailer_icon && (
            <img src={listing.retailer_icon} alt="" className="size-4 rounded-sm" referrerPolicy="no-referrer" />
          )}
          <span className="truncate">{retailer}</span>
        </div>
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 line-clamp-2 text-sm leading-snug hover:underline"
        >
          {listing.title}
        </a>
        <div className="mt-auto flex items-baseline justify-between gap-2 pt-2">
          <span className="font-semibold">{formatPrice(listing.price, listing.currency)}</span>
          {listing.rating !== null && (
            <span className="text-xs text-muted">
              ★ {listing.rating}
              {listing.reviews ? ` (${listing.reviews.toLocaleString()})` : ''}
            </span>
          )}
        </div>
        <SaveButtons
          item={{
            item_id: itemId,
            title: listing.title,
            url: listing.url,
            retailer,
            image_url: listing.image_url,
            price: listing.price,
            currency: listing.currency,
          }}
        />
      </div>
    </article>
  )
}
