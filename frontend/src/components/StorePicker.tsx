import type { Store } from '../lib/api'

interface StorePickerProps {
  stores: Store[]
  selected: string | null
  onSelect: (slug: string) => void
}

export function StorePicker({ stores, selected, onSelect }: StorePickerProps) {
  return (
    <div role="radiogroup" aria-label="Choose a store" className="grid gap-3 sm:grid-cols-3">
      {stores.map((store) => {
        const isSelected = store.slug === selected
        return (
          <button
            key={store.slug}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onSelect(store.slug)}
            className={`group relative overflow-hidden rounded-2xl border bg-card p-5 text-left transition
              focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink
              ${isSelected ? 'border-ink shadow-[0_8px_30px_-12px_rgba(28,25,23,0.35)]' : 'border-line hover:border-muted'}`}
          >
            <span
              aria-hidden
              className="absolute inset-x-0 top-0 h-1 transition-all group-hover:h-1.5"
              style={{ backgroundColor: store.accent_color }}
            />
            <span className="flex items-baseline justify-between gap-2">
              <span className="font-display text-xl">{store.name}</span>
              <span
                aria-hidden
                className={`size-3 shrink-0 rounded-full border transition
                  ${isSelected ? 'border-ink bg-ink' : 'border-muted'}`}
              />
            </span>
            <span className="mt-2 block text-sm leading-relaxed text-muted">{store.tagline}</span>
            <span className="mt-4 block text-xs uppercase tracking-[0.14em] text-muted">
              {store.product_count.toLocaleString()} pieces
            </span>
          </button>
        )
      })}
    </div>
  )
}
