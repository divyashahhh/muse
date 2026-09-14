// Typed client for the Muse API. Types mirror backend/app/schemas.py.

export type ListingKind = 'visual_match' | 'aesthetic' | 'similar_brand' | 'offer'

export interface ItemAnalysis {
  category: string
  product_name: string
  brand: string | null
  brand_confidence: 'confirmed' | 'likely' | 'unknown'
  colors: string[]
  materials: string[]
  style_tags: string[]
  gender: string
  price_tier: string
  summary: string
  exact_match_query: string
  visual_query: string
  aesthetic_queries: { label: string; query: string }[]
  similar_brands: string[]
}

export interface Item {
  id: string
  source: 'upload' | 'url'
  source_url: string | null
  image_url: string
  title: string | null
  brand: string | null
  retailer: string | null
  price: number | null
  currency: string | null
  analysis: ItemAnalysis
  created_at: string
}

export interface Listing {
  id: number
  kind: ListingKind
  group_label: string | null
  title: string
  url: string
  retailer: string | null
  retailer_icon: string | null
  image_url: string | null
  price: number | null
  currency: string | null
  shipping: number | null
  in_stock: boolean | null
  condition: string | null
  rating: number | null
  reviews: number | null
  match_reason: string | null
}

export interface DiscoverResult {
  item_id: string
  searched_at: string
  sections: { kind: ListingKind; label: string; listings: Listing[] }[]
}

export interface PriceComparison {
  item_id: string
  checked_at: string
  reference: { retailer: string | null; url: string; price: number; currency: string | null } | null
  offers: Listing[]
}

export interface RecentItem {
  id: string
  source: 'upload' | 'url'
  source_url: string | null
  image_url: string
  title: string | null
  brand: string | null
  retailer: string | null
  price: number | null
  currency: string | null
  product_name: string
  category: string
  created_at: string
  discovered_at: string | null
  prices_checked_at: string | null
}

export interface WishlistItem {
  id: number
  item_id: string | null
  title: string
  url: string
  retailer: string | null
  image_url: string | null
  price: number | null
  currency: string | null
  created_at: string
}

export type WishlistInput = Omit<WishlistItem, 'id' | 'created_at'>

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE_URL = import.meta.env.VITE_API_URL ?? ''
const CLIENT_ID_KEY = 'muse-client-id'

/** Anonymous per-browser id that scopes Recents and the wishlist until accounts exist. */
function clientId(): string {
  try {
    let id = localStorage.getItem(CLIENT_ID_KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(CLIENT_ID_KEY, id)
    }
    return id
  } catch {
    return 'anonymous-session'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Muse-Client', clientId())
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json')

  const response = await fetch(`${BASE_URL}/api${path}`, { ...init, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    // FastAPI validation errors put a list of problems in `detail`.
    const detail =
      typeof body?.detail === 'string'
        ? body.detail
        : Array.isArray(body?.detail) && typeof body.detail[0]?.msg === 'string'
          ? body.detail[0].msg
          : response.statusText
    throw new ApiError(response.status, detail || 'Something went wrong.')
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

export const api = {
  uploadItem: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Item>('/items/upload', { method: 'POST', body: form })
  },
  itemFromUrl: (url: string) =>
    request<Item>('/items/from-url', { method: 'POST', body: JSON.stringify({ url }) }),
  getItem: (id: string) => request<Item>(`/items/${id}`),
  discover: (id: string, refresh = false) =>
    request<DiscoverResult>(`/items/${id}/discover?refresh=${refresh}`, { method: 'POST' }),
  comparePrices: (id: string, refresh = false) =>
    request<PriceComparison>(`/items/${id}/prices?refresh=${refresh}`, { method: 'POST' }),

  recentItems: () => request<RecentItem[]>('/items/recent'),
  removeRecent: (id: string) => request<void>(`/items/${id}`, { method: 'DELETE' }),

  wishlist: () => request<WishlistItem[]>('/wishlist'),
  addToWishlist: (item: WishlistInput) =>
    request<WishlistItem>('/wishlist', { method: 'POST', body: JSON.stringify(item) }),
  removeFromWishlist: (id: number) => request<void>(`/wishlist/${id}`, { method: 'DELETE' }),
}
