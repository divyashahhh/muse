import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { api } from '../lib/api'
import { useLibrary } from '../library/LibraryContext'
import { LinkIcon, UploadIcon } from './Icons'

export function SearchPanel() {
  const navigate = useNavigate()
  const { refreshRecents } = useLibrary()
  const [url, setUrl] = useState('')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(create: () => Promise<{ id: string }>) {
    setWorking(true)
    setError(null)
    try {
      const item = await create()
      void refreshRecents()
      navigate(`/items/${item.id}`)
    } catch (e) {
      setError((e as Error).message)
      setWorking(false)
    }
  }

  function submitUrl(event: FormEvent) {
    event.preventDefault()
    if (url.trim()) run(() => api.itemFromUrl(url.trim()))
  }

  return (
    <div className="rounded-3xl border border-line bg-white p-3 shadow-[var(--shadow-card)]">
      <form onSubmit={submitUrl} className="flex flex-col gap-2 sm:flex-row">
        <label className="flex min-w-0 flex-1 items-center gap-3 rounded-full bg-sand px-5">
          <LinkIcon className="shrink-0 text-muted" />
          <span className="sr-only">Product link</span>
          <input
            type="url"
            required
            placeholder="Paste a product link…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={working}
            className="min-w-0 flex-1 bg-transparent py-3.5 text-[15px] outline-none placeholder:text-muted"
          />
        </label>
        <button
          type="submit"
          disabled={working}
          className="rounded-full bg-brown px-7 py-3.5 font-medium text-white transition hover:bg-brown-light disabled:opacity-60"
        >
          {working ? 'Analysing…' : 'Search'}
        </button>
      </form>

      <label
        className={`mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-full border border-dashed border-brown/30 px-5 py-3 text-sm text-brown transition hover:bg-cream ${
          working ? 'pointer-events-none opacity-60' : ''
        }`}
      >
        <UploadIcon size={18} />
        Or upload a photo / screenshot
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
        <p role="status" className="px-3 pt-3 text-center text-sm text-muted">
          Analysing your item with AI… this takes a few seconds.
        </p>
      )}
      {error && (
        <p role="alert" className="mx-1 mt-3 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      )}
      <p className="px-3 pt-3 pb-1 text-xs leading-relaxed text-muted">
        <span className="font-medium text-brown">Heads up:</span> some store links may not work.
        Many stores (for example H&amp;M, Uniqlo, Adidas, Sephora, Walmart and Target) block automated
        access. If a link fails, upload a screenshot instead.
      </p>
    </div>
  )
}
