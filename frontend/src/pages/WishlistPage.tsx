import { Link } from 'react-router'
import type { ReactNode } from 'react'

import { ExternalIcon, TrashIcon } from '../components/Icons'
import { PageBanner } from '../components/PageBanner'
import { useLibrary } from '../library/LibraryContext'
import type { WishlistItem } from '../lib/api'
import { formatPrice, hostname } from '../lib/format'
import { linksToMuse } from '../lib/wishlist'

export function WishlistPage() {
  const { wishlist, removeFromWishlist, error } = useLibrary()

  return (
    <>
      <PageBanner title="Wishlist" crumbs={[{ label: 'Home', to: '/' }, { label: 'Wishlist' }]} />
      <section className="mx-auto max-w-7xl px-4 pt-10 sm:px-6">
        {error && <p className="mb-6 text-sm text-red-700">{error}</p>}
        {wishlist.length === 0 ? (
          <div className="mx-auto max-w-md py-16 text-center">
            <h2 className="text-2xl font-medium">Your wishlist is empty</h2>
            <p className="mt-2 text-muted">
              Tap the heart on a search result or a recent search to save it here.
            </p>
            <Link
              to="/"
              className="mt-6 inline-block rounded-full bg-brown px-7 py-3 font-medium text-white hover:bg-brown-light"
            >
              Start searching
            </Link>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted">
              {wishlist.length} saved item{wishlist.length === 1 ? '' : 's'} · checkout happens on
              each retailer&rsquo;s site
            </p>
            <div className="mt-6 grid grid-cols-2 gap-x-5 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
              {wishlist.map((saved) => (
                <SavedCard
                  key={saved.id}
                  saved={saved}
                  onRemove={() => removeFromWishlist(saved.id).catch((e: Error) => alert(e.message))}
                />
              ))}
            </div>
          </>
        )}
      </section>
    </>
  )
}

function SavedCard({ saved, onRemove }: { saved: WishlistItem; onRemove: () => void }) {
  const fromMuse = linksToMuse(saved)
  // A saved search whose item was since removed from Recents has nowhere to link to.
  const itemPath = saved.item_id ? `/items/${saved.item_id}` : null

  const target = (className: string, children: ReactNode) => {
    if (!fromMuse)
      return (
        <a href={saved.url} target="_blank" rel="noopener noreferrer" className={className}>
          {children}
        </a>
      )
    return itemPath ? (
      <Link to={itemPath} className={className}>
        {children}
      </Link>
    ) : (
      <div className={className}>{children}</div>
    )
  }

  return (
    <article className="group flex flex-col">
      <div className="relative overflow-hidden rounded-2xl bg-sand">
        {target(
          'block aspect-[4/5]',
          saved.image_url && (
            <img
              src={saved.image_url}
              alt={saved.title}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="h-full w-full object-contain p-4 mix-blend-multiply transition duration-300 group-hover:scale-105"
            />
          ),
        )}
        {fromMuse && (
          <span className="absolute top-3 left-3 rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-ink shadow-sm">
            Your search
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove from wishlist"
          className="absolute top-3 right-3 flex size-9 items-center justify-center rounded-full bg-white shadow-sm transition hover:text-red-600"
        >
          <TrashIcon size={17} />
        </button>
      </div>
      <p className="mt-3 truncate text-xs text-muted">
        {saved.retailer ?? (fromMuse ? 'Saved from Muse' : hostname(saved.url))}
      </p>
      {target('mt-1 line-clamp-2 text-[15px] leading-snug hover:text-brown', saved.title)}
      {saved.price !== null && (
        <p className="mt-1.5 font-semibold text-brown">{formatPrice(saved.price, saved.currency)}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {!fromMuse && (
          <a
            href={saved.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-full bg-brown px-4 py-2 font-medium text-white hover:bg-brown-light"
          >
            Buy at retailer <ExternalIcon size={14} />
          </a>
        )}
        {itemPath && (
          <Link
            to={itemPath}
            className={
              fromMuse
                ? 'rounded-full bg-brown px-4 py-2 font-medium text-white hover:bg-brown-light'
                : 'rounded-full border border-line px-4 py-2 hover:border-brown'
            }
          >
            {fromMuse ? 'Discover & compare' : 'Compare prices'}
          </Link>
        )}
      </div>
    </article>
  )
}
