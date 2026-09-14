import { Link } from 'react-router'

import { ExternalIcon, TrashIcon } from '../components/Icons'
import { PageBanner } from '../components/PageBanner'
import { useLibrary } from '../library/LibraryContext'
import { formatPrice, hostname } from '../lib/format'

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
            <p className="mt-2 text-muted">Tap the heart on any item to save it here.</p>
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
                <article key={saved.id} className="group flex flex-col">
                  <div className="relative overflow-hidden rounded-2xl bg-sand">
                    <a href={saved.url} target="_blank" rel="noopener noreferrer" className="block aspect-[4/5]">
                      {saved.image_url && (
                        <img
                          src={saved.image_url}
                          alt={saved.title}
                          loading="lazy"
                          referrerPolicy="no-referrer"
                          className="h-full w-full object-contain p-4 mix-blend-multiply transition duration-300 group-hover:scale-105"
                        />
                      )}
                    </a>
                    <button
                      type="button"
                      onClick={() => removeFromWishlist(saved.id).catch((e: Error) => alert(e.message))}
                      aria-label="Remove from wishlist"
                      className="absolute top-3 right-3 flex size-9 items-center justify-center rounded-full bg-white shadow-sm transition hover:text-red-600"
                    >
                      <TrashIcon size={17} />
                    </button>
                  </div>
                  <p className="mt-3 truncate text-xs text-muted">{saved.retailer ?? hostname(saved.url)}</p>
                  <a
                    href={saved.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 line-clamp-2 text-[15px] leading-snug hover:text-brown"
                  >
                    {saved.title}
                  </a>
                  <p className="mt-1.5 font-semibold text-brown">{formatPrice(saved.price, saved.currency)}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <a
                      href={saved.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 rounded-full bg-brown px-4 py-2 font-medium text-white hover:bg-brown-light"
                    >
                      Buy at retailer <ExternalIcon size={14} />
                    </a>
                    {saved.item_id && (
                      <Link
                        to={`/items/${saved.item_id}`}
                        className="rounded-full border border-line px-4 py-2 hover:border-brown"
                      >
                        Compare prices
                      </Link>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </>
  )
}
