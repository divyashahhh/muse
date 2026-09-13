/** Format a price whose currency may be an ISO code ("USD") or a symbol ("$") from search results. */
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
