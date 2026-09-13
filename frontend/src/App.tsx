import { useState } from 'react'

import { StorePicker } from './components/StorePicker'
import { useApi } from './hooks/useApi'
import { api } from './lib/api'

export default function App() {
  const stores = useApi(api.stores)
  const [selectedStore, setSelectedStore] = useState<string | null>(null)

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <a href="/" className="font-display text-2xl italic tracking-tight">
            muse
          </a>
          <span className="text-xs uppercase tracking-[0.18em] text-muted">AI Stylist</span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-16 sm:py-24">
        <section className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.18em] text-clay">One piece in, a whole look out</p>
          <h1 className="mt-4 font-display text-5xl leading-[1.05] font-light sm:text-6xl">
            Show us something you love. <em className="font-normal">We&rsquo;ll style the rest.</em>
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted">
            Muse reads the aesthetic of a single item — its vibe, palette, silhouette and formality — and
            curates a complete, explained outfit from the store you choose.
          </p>
        </section>

        <section className="mt-16" aria-labelledby="store-heading">
          <h2 id="store-heading" className="font-display text-2xl">
            Choose a store
          </h2>
          <div className="mt-6">
            {stores.status === 'loading' && <StoreSkeleton />}
            {stores.status === 'error' && (
              <p role="alert" className="rounded-2xl border border-line bg-card p-5 text-sm text-muted">
                Couldn&rsquo;t reach the Muse API ({stores.error.message}). Is the backend running?
              </p>
            )}
            {stores.status === 'success' && (
              <StorePicker stores={stores.data} selected={selectedStore} onSelect={setSelectedStore} />
            )}
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-6xl px-6 py-6 text-xs leading-relaxed text-muted">
          Muse is a portfolio project. Stores are fictional and catalog data comes from a licensed
          public fashion dataset — prices and inventory are illustrative, not live.
        </p>
      </footer>
    </div>
  )
}

function StoreSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-36 animate-pulse rounded-2xl border border-line bg-card" />
      ))}
    </div>
  )
}
