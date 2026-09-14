/** Format a price whose currency may be an ISO code ("USD") or a symbol ("$"). */
export function formatPrice(amount: number | null, currency: string | null): string {
  if (amount === null) return '—'
  if (currency && /^[A-Z]{3}$/.test(currency)) {
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
    } catch {
      // Unknown ISO code: fall through to plain formatting.
    }
  }
  const value = amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return currency ? `${currency}${value}` : value
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  const units: [number, string][] = [
    [60 * 60 * 24 * 7, 'w'],
    [60 * 60 * 24, 'd'],
    [60 * 60, 'h'],
    [60, 'm'],
  ]
  for (const [size, label] of units) {
    if (seconds >= size) return `${Math.floor(seconds / size)}${label} ago`
  }
  return 'just now'
}

// Colour words the AI returns that CSS doesn't know by name.
const COLOR_ALIASES: Record<string, string> = {
  bone: '#e3dac9', camel: '#c19a6b', cognac: '#9a463d', nude: '#e3bc9a', taupe: '#8b7d6b',
  charcoal: '#36454f', burgundy: '#800020', rust: '#b7410e', mustard: '#e1ad01', blush: '#de5d83',
  champagne: '#f7e7ce', denim: '#1560bd', gum: '#c58b4d', cream: '#f5efe0', stone: '#b8ad9e',
  sand: '#d8c3a5', mocha: '#6f4e37', cherry: '#990f2b', sage: '#9caf88', ecru: '#e6dcc4',
  natural: '#e8dcc8', multicolor: 'conic-gradient(red, orange, yellow, green, blue, purple, red)',
}

/** A CSS colour (or gradient) for a colour name, or null if we can't show it. */
export function swatchFor(name: string): string | null {
  const key = name.trim().toLowerCase()
  const last = key.split(/\s+/).at(-1) ?? key
  for (const candidate of [key.replace(/\s+/g, ''), last]) {
    if (COLOR_ALIASES[candidate]) return COLOR_ALIASES[candidate]
    if (typeof CSS !== 'undefined' && CSS.supports('color', candidate)) return candidate
  }
  return null
}
