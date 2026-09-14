import type { Listing } from '../lib/api'
import { formatPrice, hostname } from '../lib/format'
import { HeartButton } from './HeartButton'
import { StarIcon } from './Icons'

export function ListingCard({ listing, itemId }: { listing: Listing; itemId: string }) {
  const retailer = listing.retailer ?? hostname(listing.url)
  const badge = listing.condition ?? (listing.in_stock === false ? 'Sold out' : null)

  return (
    <article className="group flex flex-col">
      <div className="relative overflow-hidden rounded-2xl bg-sand">
        <a href={listing.url} target="_blank" rel="noopener noreferrer" className="block aspect-[4/5]">
          {listing.image_url ? (
            <img
              src={listing.image_url}
              alt={listing.title}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="h-full w-full object-contain p-4 mix-blend-multiply transition duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">No image</div>
          )}
        </a>
        {badge && (
          <span className="absolute top-3 left-3 rounded-full bg-mustard px-2.5 py-1 text-[11px] font-medium text-ink">
            {badge}
          </span>
        )}
        <div className="absolute top-3 right-3">
          <HeartButton
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
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted">
        <span className="truncate">{retailer}</span>
        {listing.rating !== null && (
          <span className="flex shrink-0 items-center gap-1 text-ink">
            <StarIcon size={13} className="text-mustard" />
            {listing.rating}
          </span>
        )}
      </div>
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 line-clamp-2 text-[15px] leading-snug hover:text-brown"
      >
        {listing.title}
      </a>
      <p className="mt-1.5 font-semibold text-brown">
        {formatPrice(listing.price, listing.currency)}
        {listing.shipping !== null && listing.shipping > 0 && (
          <span className="ml-1.5 text-xs font-normal text-muted">
            + {formatPrice(listing.shipping, listing.currency)} shipping
          </span>
        )}
      </p>
    </article>
  )
}
