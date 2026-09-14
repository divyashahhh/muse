import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { HeartButton } from '../components/HeartButton'
import { ExternalIcon, ShieldCheckIcon, SparkleIcon, StarIcon } from '../components/Icons'
import { ListingCard } from '../components/ListingCard'
import { useRequest } from '../hooks/useRequest'
import { api } from '../lib/api'
import type { Item, Listing, ListingKind } from '../lib/api'
import { formatPrice, hostname, swatchFor } from '../lib/format'
import { wishlistInputForItem } from '../lib/wishlist'

type Tab = 'discover' | 'prices'

export function ItemPage() {
  const { id = '' } = useParams()
  return <ItemView key={id} id={id} />
}

function ItemView({ id }: { id: string }) {
  const [item] = useRequest(() => api.getItem(id))
  const [tab, setTab] = useState<Tab>('discover')
  // Price comparison spends search quota, so it only starts once its tab is first opened.
  const [pricesOpened, setPricesOpened] = useState(false)

  if (item.status === 'loading') return <PageMessage>Loading…</PageMessage>
  if (item.status === 'error')
    return (
      <PageMessage>
        <ErrorBox message={item.error} />
      </PageMessage>
    )

  const data = item.data
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      <nav aria-label="Breadcrumb" className="py-6 text-sm text-muted">
        <Link to="/" className="hover:text-brown">Home</Link>
        <span className="mx-2">/</span>
        <Link to="/recents" className="hover:text-brown">Recents</Link>
        <span className="mx-2">/</span>
        <span className="text-ink">{data.analysis.category}</span>
      </nav>

      <ItemDetails item={data} />

      <div role="tablist" className="mt-16 flex justify-center gap-10 border-b border-line">
        {(
          [
            ['discover', 'Discover Similar'],
            ['prices', 'Compare Prices'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => {
              setTab(value)
              if (value === 'prices') setPricesOpened(true)
            }}
            className={`-mb-px border-b-2 px-1 pb-4 text-[17px] transition ${
              tab === value ? 'border-brown font-medium text-brown' : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="pt-10">
        {/* Tabs stay mounted once opened so switching back doesn't reload. */}
        <div hidden={tab !== 'discover'}>
          <DiscoverTab item={data} />
        </div>
        {pricesOpened && (
          <div hidden={tab !== 'prices'}>
            <PricesTab item={data} />
          </div>
        )}
      </div>
    </div>
  )
}

function ItemDetails({ item }: { item: Item }) {
  const a = item.analysis
  const colorSwatches = a.colors.map((name) => ({ name, css: swatchFor(name) }))

  return (
    <section className="grid gap-10 lg:grid-cols-2">
      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-3xl bg-sand">
        <img src={item.image_url} alt={a.product_name} className="h-full w-full object-contain p-8 mix-blend-multiply" />
      </div>

      <div className="lg:py-4">
        <p className="text-sm text-muted capitalize">{a.category}</p>
        <div className="mt-2 flex items-start justify-between gap-4">
          <h1 className="text-3xl leading-tight font-medium sm:text-4xl">{item.title ?? a.product_name}</h1>
          <span className="mt-2 flex shrink-0 items-center gap-1 text-sm">
            <StarIcon size={16} className="text-mustard" />
            <span className="capitalize">{a.price_tier !== 'unknown' ? a.price_tier : 'Style'}</span>
          </span>
        </div>

        {(item.brand || a.brand) && (
          <p className="mt-2 text-muted">
            by <span className="font-medium text-ink">{item.brand ?? a.brand}</span>
            {!item.brand && a.brand_confidence !== 'confirmed' && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-cream px-2 py-0.5 text-xs text-brown">
                <SparkleIcon size={12} /> identified by AI
              </span>
            )}
          </p>
        )}

        {item.price !== null && (
          <p className="mt-5 text-3xl font-semibold text-brown">
            {formatPrice(item.price, item.currency)}
            {item.retailer && <span className="ml-3 text-base font-normal text-muted">at {item.retailer}</span>}
          </p>
        )}

        <p className="mt-5 leading-relaxed text-muted">{a.summary}</p>

        {colorSwatches.length > 0 && (
          <div className="mt-6">
            <p className="text-sm">
              Color : <span className="text-muted capitalize">{a.colors.join(', ')}</span>
            </p>
            <div className="mt-3 flex gap-3">
              {colorSwatches.map(({ name, css }) => (
                <span
                  key={name}
                  title={name}
                  className="size-8 rounded-full border border-line ring-2 ring-white ring-offset-1 ring-offset-line"
                  style={{ background: css ?? 'repeating-linear-gradient(45deg,#eee 0 4px,#fff 4px 8px)' }}
                />
              ))}
            </div>
          </div>
        )}

        {a.materials.length > 0 && (
          <div className="mt-6">
            <p className="text-sm">Material :</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {a.materials.map((m) => (
                <span key={m} className="rounded-lg border border-line px-3.5 py-1.5 text-sm capitalize">
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}

        {a.style_tags.length > 0 && (
          <div className="mt-6">
            <p className="text-sm">Style :</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {a.style_tags.map((tag) => (
                <span key={tag} className="rounded-full bg-cream px-3.5 py-1.5 text-sm text-brown capitalize">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 flex items-center gap-3">
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-1 items-center justify-center gap-2 rounded-full bg-brown px-8 py-3.5 font-medium text-white transition hover:bg-brown-light sm:flex-none"
            >
              View on {hostname(item.source_url)} <ExternalIcon size={16} />
            </a>
          ) : (
            <p className="text-sm text-muted">Save this item to come back to it later</p>
          )}
          <HeartButton variant="outline" item={wishlistInputForItem(item)} />
        </div>

        <dl className="mt-8 space-y-2 border-t border-line pt-6 text-sm">
          <div className="flex gap-2">
            <dt className="text-muted">Identified as :</dt>
            <dd>{a.product_name}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-muted">Searched from :</dt>
            <dd>{item.source === 'url' ? 'Product link' : 'Uploaded photo'}</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

const SECTION_EYEBROWS: Record<Exclude<ListingKind, 'offer'>, string> = {
  visual_match: 'Visually similar',
  aesthetic: 'Same aesthetic',
  similar_brand: 'From similar brands',
}

function DiscoverTab({ item }: { item: Item }) {
  const [result, reload] = useRequest((refresh) => api.discover(item.id, refresh))

  if (result.status === 'loading')
    return <LoadingNote>Searching stores and filtering results with AI… (up to ~40 seconds)</LoadingNote>
  if (result.status === 'error') return <ErrorBox message={result.error} onRetry={reload} />

  const { sections } = result.data
  return (
    <div className="space-y-16">
      {sections.length === 0 && <p className="text-center text-muted">No results found for this item.</p>}
      {sections.map((section) => (
        <section key={`${section.kind}-${section.label}`}>
          <div className="text-center">
            <p className="text-sm text-muted">{SECTION_EYEBROWS[section.kind as keyof typeof SECTION_EYEBROWS]}</p>
            <h2 className="mt-1 text-3xl font-medium">{section.label}</h2>
          </div>
          <div className="mt-8 grid grid-cols-2 gap-x-5 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
            {section.listings.map((listing) => (
              <ListingCard key={listing.id} listing={listing} itemId={item.id} />
            ))}
          </div>
        </section>
      ))}
      <RefreshNote at={result.data.searched_at} onRefresh={reload} />
    </div>
  )
}

const total = (o: Pick<Listing, 'price' | 'shipping'>) => (o.price ?? 0) + (o.shipping ?? 0)

function PricesTab({ item }: { item: Item }) {
  const [result, reload] = useRequest((refresh) => api.comparePrices(item.id, refresh))

  if (result.status === 'loading')
    return <LoadingNote>Checking stores and verifying matches with AI… (up to ~40 seconds)</LoadingNote>
  if (result.status === 'error') return <ErrorBox message={result.error} onRetry={reload} />

  const { offers, reference } = result.data
  const cheapest = offers[0]
  // Only compare like with like: sources can return different currencies.
  const saving =
    reference && cheapest && reference.currency === cheapest.currency && total(cheapest) < reference.price
      ? reference.price - total(cheapest)
      : null

  return (
    <div className="mx-auto max-w-4xl">
      {cheapest && (
        <div className="mb-8 flex flex-col gap-4 rounded-3xl bg-brown p-6 text-white sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-white/70">Best price found</p>
            <p className="mt-1 text-3xl font-semibold">
              {formatPrice(total(cheapest), cheapest.currency)}
              <span className="ml-2 text-base font-normal text-white/70">at {cheapest.retailer}</span>
            </p>
            {saving !== null && (
              <p className="mt-1 text-sm text-mustard">{formatPrice(saving, cheapest.currency)} less than your link</p>
            )}
          </div>
          <a
            href={cheapest.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 rounded-full bg-mustard px-7 py-3 font-medium text-ink hover:brightness-95"
          >
            View deal <ExternalIcon size={16} />
          </a>
        </div>
      )}

      {offers.length === 0 && !reference ? (
        <p className="text-center text-muted">We couldn&rsquo;t find this exact item at other retailers.</p>
      ) : (
        <ul className="space-y-3">
          {reference && (
            <li className="flex flex-wrap items-center gap-4 rounded-2xl border border-dashed border-line bg-sand/60 p-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{reference.retailer ?? hostname(reference.url)}</p>
                <p className="text-sm text-muted">Your original link</p>
              </div>
              <p className="text-lg font-semibold">{formatPrice(reference.price, reference.currency)}</p>
            </li>
          )}
          {offers.map((offer, i) => (
            <li key={offer.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-line p-4 transition hover:shadow-[var(--shadow-card)]">
              <div className="size-16 shrink-0 overflow-hidden rounded-xl bg-sand">
                {(offer.image_url ?? item.image_url) && (
                  <img
                    src={offer.image_url ?? item.image_url}
                    alt=""
                    referrerPolicy="no-referrer"
                    className="h-full w-full object-contain p-1 mix-blend-multiply"
                  />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{offer.retailer ?? hostname(offer.url)}</p>
                  {i === 0 && <span className="rounded-full bg-mustard px-2.5 py-0.5 text-xs font-medium">Cheapest</span>}
                  {offer.condition && <span className="rounded-full bg-cream px-2.5 py-0.5 text-xs text-brown">{offer.condition}</span>}
                </div>
                <p className="mt-1 flex items-start gap-1.5 text-xs text-muted">
                  <ShieldCheckIcon size={14} className="mt-px shrink-0 text-success" /> {offer.match_reason}
                </p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold text-brown">{formatPrice(total(offer), offer.currency)}</p>
                <p className="text-xs text-muted">
                  {offer.shipping === null
                    ? 'Shipping not listed'
                    : offer.shipping === 0
                      ? 'Free shipping'
                      : `incl. ${formatPrice(offer.shipping, offer.currency)} shipping`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={offer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full bg-brown px-5 py-2.5 text-sm font-medium whitespace-nowrap text-white hover:bg-brown-light"
                >
                  View deal
                </a>
                <HeartButton
                  item={{
                    item_id: item.id,
                    title: offer.title,
                    url: offer.url,
                    retailer: offer.retailer,
                    image_url: offer.image_url ?? item.image_url,
                    price: offer.price,
                    currency: offer.currency,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-6 text-center text-xs leading-relaxed text-muted">
        Prices are read from each retailer&rsquo;s product page or eBay listing and may have changed.
        Matches are verified by AI (or by barcode).
      </p>
      <RefreshNote at={result.data.checked_at} onRefresh={reload} />
    </div>
  )
}

function RefreshNote({ at, onRefresh }: { at: string; onRefresh: () => void }) {
  return (
    <p className="mt-6 text-center text-xs text-muted">
      Searched {new Date(at).toLocaleString()} ·{' '}
      <button type="button" onClick={onRefresh} className="font-medium text-brown underline">
        Search again
      </button>
    </p>
  )
}

function LoadingNote({ children }: { children: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-10 text-center text-muted">
      <span className="size-9 animate-spin rounded-full border-2 border-line border-t-brown" />
      <p>{children}</p>
    </div>
  )
}

function PageMessage({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-7xl px-4 py-16 text-muted sm:px-6">{children}</div>
}

function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-2xl rounded-2xl bg-red-50 p-4 text-center text-sm text-red-800">
      {message}
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-3 font-medium underline">
          Try again
        </button>
      )}
    </div>
  )
}
