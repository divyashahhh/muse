import { useState } from 'react'
import { useParams } from 'react-router'

import { ListingCard } from '../components/ListingCard'
import { SaveButtons } from '../components/SaveButtons'
import { useRequest } from '../hooks/useRequest'
import { api } from '../lib/api'
import type { Item, ListingKind } from '../lib/api'
import { formatPrice, hostname } from '../lib/format'

type Tab = 'discover' | 'prices'

export function ItemPage() {
  const { id = '' } = useParams()
  return <ItemView key={id} id={id} />
}

function ItemView({ id }: { id: string }) {
  const [item] = useRequest(() => api.getItem(id))
  const [tab, setTab] = useState<Tab>('discover')
  // Price comparison spends searches, so it only starts once its tab is first opened.
  const [pricesOpened, setPricesOpened] = useState(false)

  if (item.status === 'loading') return <p className="text-muted">Loading…</p>
  if (item.status === 'error') return <ErrorBox message={item.error} />

  return (
    <div>
      <ItemSummary item={item.data} />

      <div role="tablist" className="mt-10 flex gap-6 border-b border-line">
        {(
          [
            ['discover', 'Discover similar'],
            ['prices', 'Compare prices'],
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
            className={`-mb-px border-b-2 pb-3 text-sm font-medium ${
              tab === value ? 'border-ink' : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-8">
        {/* Tabs stay mounted once opened so switching back doesn't reload. */}
        <div hidden={tab !== 'discover'}>
          <DiscoverTab item={item.data} />
        </div>
        {pricesOpened && (
          <div hidden={tab !== 'prices'}>
            <PricesTab item={item.data} />
          </div>
        )}
      </div>
    </div>
  )
}

function ItemSummary({ item }: { item: Item }) {
  const a = item.analysis
  return (
    <section className="grid gap-8 sm:grid-cols-[240px_1fr]">
      <img
        src={item.image_url}
        alt={a.product_name}
        className="aspect-square w-full rounded-xl border border-line bg-white object-contain p-2"
      />
      <div>
        <p className="text-xs uppercase tracking-widest text-muted">{a.category}</p>
        <h1 className="mt-2 font-display text-3xl leading-tight">{item.title ?? a.product_name}</h1>
        {a.brand && (
          <p className="mt-1 text-muted">
            {a.brand}
            {a.brand_confidence !== 'confirmed' && !item.brand && ' (identified by AI)'}
          </p>
        )}
        {item.price !== null && (
          <p className="mt-3 text-xl font-semibold">
            {formatPrice(item.price, item.currency)}
            {item.retailer && <span className="ml-2 text-sm font-normal text-muted">at {item.retailer}</span>}
          </p>
        )}
        <p className="mt-4 leading-relaxed">{a.summary}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {[...a.style_tags, ...a.colors, ...a.materials].map((tag, i) => (
            <span key={`${tag}-${i}`} className="rounded-full bg-line/60 px-3 py-1 text-xs">
              {tag}
            </span>
          ))}
        </div>
        {item.source_url && (
          <>
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-sm underline"
            >
              View original on {hostname(item.source_url)}
            </a>
            <SaveButtons
              item={{
                item_id: item.id,
                title: item.title ?? a.product_name,
                url: item.source_url,
                retailer: item.retailer,
                image_url: item.image_url,
                price: item.price,
                currency: item.currency,
              }}
            />
          </>
        )}
      </div>
    </section>
  )
}

const SECTION_HEADINGS: Record<Exclude<ListingKind, 'offer'>, string> = {
  visual_match: 'Visually similar',
  aesthetic: 'Same aesthetic',
  similar_brand: 'From similar brands',
}

function DiscoverTab({ item }: { item: Item }) {
  const [result, reload] = useRequest((refresh) => api.discover(item.id, refresh))

  if (result.status === 'loading')
    return <p className="text-muted">Searching retailers for similar items… (up to ~20 seconds)</p>
  if (result.status === 'error') return <ErrorBox message={result.error} onRetry={reload} />

  const { sections } = result.data
  return (
    <div className="space-y-12">
      {!item.visual_search_available && (
        <p className="rounded-lg bg-line/40 p-3 text-sm text-muted">
          Visual image search needs cloud image storage, which isn&rsquo;t configured — showing
          AI-matched results only.
        </p>
      )}
      {sections.length === 0 && <p className="text-muted">No results found for this item.</p>}
      {sections.map((section) => (
        <section key={`${section.kind}-${section.label}`}>
          <p className="text-xs uppercase tracking-widest text-muted">
            {SECTION_HEADINGS[section.kind as keyof typeof SECTION_HEADINGS]}
          </p>
          <h2 className="mt-1 font-display text-2xl">{section.label}</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
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

function PricesTab({ item }: { item: Item }) {
  const [result, reload] = useRequest((refresh) => api.comparePrices(item.id, refresh))

  if (result.status === 'loading')
    return <p className="text-muted">Checking retailers and verifying matches… (up to ~30 seconds)</p>
  if (result.status === 'error') return <ErrorBox message={result.error} onRetry={reload} />

  const { offers, reference } = result.data
  const cheapest = offers[0]
  const total = (o: { price: number | null; shipping: number | null }) => (o.price ?? 0) + (o.shipping ?? 0)
  const saving =
    reference && cheapest && total(cheapest) < reference.price ? reference.price - total(cheapest) : null

  return (
    <div>
      {cheapest && (
        <div className="mb-6 rounded-xl border border-line bg-card p-5">
          <p className="text-sm text-muted">Best price found</p>
          <p className="mt-1 text-2xl font-semibold">
            {formatPrice(total(cheapest), cheapest.currency)}{' '}
            <span className="text-base font-normal text-muted">at {cheapest.retailer}</span>
          </p>
          {saving !== null && (
            <p className="mt-1 text-sm text-green-700">
              {formatPrice(saving, cheapest.currency)} less than your link
            </p>
          )}
        </div>
      )}

      {offers.length === 0 ? (
        <p className="text-muted">We couldn&rsquo;t find this exact item at other retailers.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-line text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="p-3">Retailer</th>
                <th className="p-3">Price</th>
                <th className="p-3">Shipping</th>
                <th className="p-3">Total</th>
                <th className="p-3">Why it matches</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {reference && (
                <tr className="border-b border-line bg-paper/60">
                  <td className="p-3">{reference.retailer ?? hostname(reference.url)} <span className="text-xs text-muted">(your link)</span></td>
                  <td className="p-3">{formatPrice(reference.price, reference.currency)}</td>
                  <td className="p-3 text-muted">—</td>
                  <td className="p-3">{formatPrice(reference.price, reference.currency)}</td>
                  <td className="p-3 text-muted">Original listing</td>
                  <td className="p-3" />
                </tr>
              )}
              {offers.map((offer, i) => (
                <tr key={offer.id} className="border-b border-line last:border-0">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      {offer.retailer_icon && (
                        <img src={offer.retailer_icon} alt="" className="size-5 rounded-sm" referrerPolicy="no-referrer" />
                      )}
                      <span className="font-medium">{offer.retailer ?? hostname(offer.url)}</span>
                      {i === 0 && <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-800">Cheapest</span>}
                    </div>
                    {offer.condition && <span className="text-xs text-muted">{offer.condition}</span>}
                  </td>
                  <td className="p-3">{formatPrice(offer.price, offer.currency)}</td>
                  <td className="p-3">
                    {offer.shipping === null ? <span className="text-muted">—</span> : offer.shipping === 0 ? 'Free' : formatPrice(offer.shipping, offer.currency)}
                  </td>
                  <td className="p-3 font-semibold">{formatPrice(total(offer), offer.currency)}</td>
                  <td className="p-3 text-xs text-muted">{offer.match_reason}</td>
                  <td className="p-3">
                    <div className="flex flex-col items-end gap-2">
                      <a
                        href={offer.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-full bg-ink px-4 py-1.5 text-xs font-medium whitespace-nowrap text-paper"
                      >
                        View deal
                      </a>
                      <SaveButtons
                        compact
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        Prices come from retailer listings indexed by Google Shopping and may have changed. Shipping
        shown where the retailer lists it. Matches are verified by AI.
      </p>
      <RefreshNote at={result.data.checked_at} onRefresh={reload} />
    </div>
  )
}

function RefreshNote({ at, onRefresh }: { at: string; onRefresh: () => void }) {
  return (
    <p className="mt-4 text-xs text-muted">
      Searched {new Date(at).toLocaleString()} ·{' '}
      <button type="button" onClick={onRefresh} className="underline">
        Search again
      </button>
    </p>
  )
}

function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      {message}
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-3 underline">
          Try again
        </button>
      )}
    </div>
  )
}
