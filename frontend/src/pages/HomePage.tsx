import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { api } from '../lib/api'

export function HomePage() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [status, setStatus] = useState<'idle' | 'working'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function run(create: () => Promise<{ id: string }>) {
    setStatus('working')
    setError(null)
    try {
      const item = await create()
      navigate(`/items/${item.id}`)
    } catch (e) {
      setError((e as Error).message)
      setStatus('idle')
    }
  }

  function submitUrl(event: FormEvent) {
    event.preventDefault()
    if (url.trim()) run(() => api.itemFromUrl(url.trim()))
  }

  const working = status === 'working'

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-4xl leading-tight font-light sm:text-5xl">
        Found something you love?
      </h1>
      <p className="mt-4 text-lg text-muted">
        Show Muse one item. We&rsquo;ll find where it&rsquo;s cheapest, and a whole marketplace of
        pieces in the same style.
      </p>

      <form onSubmit={submitUrl} className="mt-10">
        <label htmlFor="url" className="text-sm font-medium">
          Paste a product link
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            id="url"
            type="url"
            required
            placeholder="https://www.example.com/products/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={working}
            className="min-w-0 flex-1 rounded-lg border border-line bg-card px-4 py-3 outline-none focus:border-ink"
          />
          <button
            type="submit"
            disabled={working}
            className="rounded-lg bg-ink px-6 py-3 font-medium text-paper disabled:opacity-50"
          >
            Search
          </button>
        </div>
        <p
          role="note"
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-relaxed text-amber-900"
        >
          <strong className="font-semibold">Heads up:</strong> some links may not work. Many stores
          (for example H&amp;M, Uniqlo, Adidas, Sephora, Walmart and Target) block automated access
          to their pages, and some only load product details in the browser. If a link doesn&rsquo;t
          work, upload a screenshot of the item instead. It works just as well.
        </p>
      </form>

      <div className="my-6 flex items-center gap-4 text-xs uppercase tracking-widest text-muted">
        <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
      </div>

      <label
        className={`flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-line bg-card px-6 py-10 text-center hover:border-ink ${
          working ? 'pointer-events-none opacity-50' : ''
        }`}
      >
        <span className="font-medium">Upload a photo</span>
        <span className="mt-1 text-sm text-muted">A screenshot or picture of the item · up to 10 MB</span>
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          disabled={working}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) run(() => api.uploadItem(file))
            e.target.value = ''
          }}
        />
      </label>

      {working && (
        <p role="status" className="mt-6 text-center text-muted">
          Analysing your item… this takes a few seconds.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </p>
      )}
    </div>
  )
}
