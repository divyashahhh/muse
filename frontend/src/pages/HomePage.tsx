import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { ArrowRightIcon, HeartIcon, ShieldCheckIcon, SparkleIcon, StoreIcon, TagIcon } from '../components/Icons'
import { DotCluster } from '../components/PageBanner'
import { RecentCard } from '../components/RecentCard'
import { SearchPanel } from '../components/SearchPanel'
import { useLibrary } from '../library/LibraryContext'
import { formatPrice } from '../lib/format'

export function HomePage() {
  const { recents, wishlist } = useLibrary()

  return (
    <>
      <Hero />
      <Features />

      <section className="mx-auto max-w-7xl px-4 pt-16 sm:px-6">
        <div className="grid gap-5 md:grid-cols-2 md:grid-rows-2">
          <FeatureCard
            className="md:row-span-2"
            count="Feature 01"
            title="Discover Similar"
            text="Look-alikes, pieces in the same aesthetic, and the same kind of item from brands with a similar vibe."
            points={['Looks like this', 'Same aesthetic', 'Similar brands']}
            images={recents.slice(0, 3).map((r) => r.image_url)}
            icon={<SparkleIcon size={44} />}
            tone="bg-cream"
          />
          <FeatureCard
            count="Feature 02"
            title="Compare Prices"
            text="The exact same product at other retailers and resellers, verified by AI, cheapest first."
            icon={<TagIcon size={44} />}
            tone="bg-sand"
          />
          <FeatureCard
            count={`${wishlist.length} saved`}
            title="Your Wishlist"
            text="Heart anything you find and come back to it any time."
            images={wishlist.slice(0, 3).flatMap((w) => (w.image_url ? [w.image_url] : []))}
            icon={<HeartIcon size={44} />}
            tone="bg-sand"
            to="/wishlist"
          />
        </div>
      </section>

      {recents.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
          <SectionHeading eyebrow="Pick up where you left off" title="Your Recent Searches" to="/recents" />
          <div className="mt-8 grid grid-cols-2 gap-x-5 gap-y-8 md:grid-cols-4">
            {recents.slice(0, 4).map((item) => (
              <RecentCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}

function Hero() {
  const { recents } = useLibrary()
  const showcase = recents.slice(0, 3)
  const priced = recents.find((r) => r.price !== null)

  return (
    <section className="relative overflow-hidden">
      <DotCluster className="absolute top-10 left-[46%] hidden lg:block" />
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:py-20">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-cream px-4 py-2 text-sm text-brown">
            <SparkleIcon size={16} /> AI-powered shopping search
          </span>
          <h1 className="mt-6 text-4xl leading-[1.1] font-medium sm:text-5xl lg:text-[3.4rem]">
            Step into Style: <br className="hidden sm:block" />
            Find It Once, <span className="text-brown">Shop It Smarter</span>
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-muted">
            Show Muse one item you love. We&rsquo;ll find where it&rsquo;s cheapest and a whole
            marketplace of pieces in the same style.
          </p>
          <div className="mt-8 max-w-xl">
            <SearchPanel />
          </div>
        </div>

        <div className="relative mx-auto hidden aspect-square w-full max-w-[520px] sm:block">
          <div className="absolute inset-x-6 top-10 bottom-0 rounded-t-full bg-brown" />
          <span className="absolute top-2 left-2 size-12 rounded-full bg-brown" />
          <span className="absolute right-4 bottom-16 size-9 rounded-full bg-mustard" />

          <div className="absolute inset-x-16 top-24 bottom-10 grid grid-cols-2 gap-3">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={`overflow-hidden rounded-3xl bg-white shadow-[var(--shadow-card)] ${i === 0 ? 'row-span-2' : ''}`}
              >
                {showcase[i] ? (
                  <img src={showcase[i].image_url} alt="" className="h-full w-full object-contain p-3" />
                ) : (
                  <div className="flex h-full items-center justify-center text-brown/30">
                    {[<StoreIcon key="s" size={56} />, <TagIcon key="t" size={44} />, <HeartIcon key="h" size={44} />][i]}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="absolute top-32 -left-2 flex items-center gap-3 rounded-2xl bg-white px-4 py-3 shadow-[var(--shadow-card)]">
            <span className="flex size-10 items-center justify-center rounded-full bg-cream text-brown">
              <TagIcon size={20} />
            </span>
            <div className="text-sm">
              <p className="text-muted">Best price found</p>
              <p className="font-semibold text-brown">
                {priced ? formatPrice(priced.price, priced.currency) : 'Across retailers'}
              </p>
            </div>
          </div>
          <div className="absolute right-0 bottom-28 flex items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm shadow-[var(--shadow-card)]">
            <ShieldCheckIcon size={18} className="text-success" /> Same product verified
          </div>
        </div>
      </div>
    </section>
  )
}

function Features() {
  const features = [
    { icon: <StoreIcon size={30} />, title: 'Real Retailer Listings', text: 'From stores, marketplaces & resellers' },
    { icon: <ShieldCheckIcon size={30} />, title: 'Verified Price Matches', text: 'Only the exact same product' },
    { icon: <HeartIcon size={30} />, title: 'Wishlist & Recents', text: 'Pick up right where you left off' },
  ]
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6">
      <div className="grid gap-6 rounded-3xl border border-line px-6 py-7 sm:grid-cols-3">
        {features.map((f) => (
          <div key={f.title} className="flex items-center gap-4">
            <span className="text-brown">{f.icon}</span>
            <div>
              <p className="font-medium">{f.title}</p>
              <p className="text-sm text-muted">{f.text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function FeatureCard({
  count,
  title,
  text,
  points,
  images = [],
  icon,
  tone,
  to,
  className = '',
}: {
  count: string
  title: string
  text: string
  points?: string[]
  images?: string[]
  icon: ReactNode
  tone: string
  to?: string
  className?: string
}) {
  const body = (
    <div className={`relative flex h-full min-h-56 overflow-hidden rounded-3xl p-7 ${tone} ${className}`}>
      <div className="relative z-10 max-w-[60%]">
        <span className="inline-block rounded-full bg-white px-3 py-1 text-xs font-medium">{count}</span>
        <h3 className="mt-4 text-3xl font-medium">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted">{text}</p>
        {points && (
          <ul className="mt-5 space-y-1.5 text-sm">
            {points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="absolute right-6 bottom-6 flex items-end gap-2">
        {images.length > 0 ? (
          images.map((src, i) => (
            <img
              key={src + i}
              src={src}
              alt=""
              referrerPolicy="no-referrer"
              className={`rounded-2xl bg-white object-contain p-2 shadow-sm ${i === 0 ? 'size-28 sm:size-32' : 'size-20 sm:size-24'}`}
            />
          ))
        ) : (
          <span className="flex size-28 items-center justify-center rounded-full bg-white/70 text-brown">{icon}</span>
        )}
      </div>
    </div>
  )
  return to ? (
    <Link to={to} className={`block ${className}`}>
      {body}
    </Link>
  ) : (
    body
  )
}

export function SectionHeading({ eyebrow, title, to }: { eyebrow: string; title: string; to?: string }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        <p className="text-sm text-muted">{eyebrow}</p>
        <h2 className="mt-1 text-3xl font-medium">{title}</h2>
      </div>
      {to && (
        <Link to={to} className="flex items-center gap-1.5 text-sm font-medium text-brown hover:underline">
          See all <ArrowRightIcon size={16} />
        </Link>
      )}
    </div>
  )
}
