// Typed client for the Muse API. Types mirror backend/app/schemas.py.

export type Category = 'top' | 'bottom' | 'dress' | 'outerwear' | 'footwear' | 'bag' | 'accessory'

export interface Health {
  status: 'ok' | 'degraded'
  database: string
}

export interface Store {
  id: number
  slug: string
  name: string
  tagline: string
  accent_color: string
  product_count: number
}

export interface Product {
  id: number
  store_id: number
  title: string
  brand: string | null
  category: Category
  subcategory: string | null
  base_color: string | null
  price_cents: number
  currency: string
  image_url: string
  product_url: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}/api${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>('/health', { signal }),

  stores: (signal?: AbortSignal) => request<Store[]>('/stores', { signal }),

  storeProducts: (
    slug: string,
    params: { category?: Category; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ) => {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([, value]) => value !== undefined)
        .map(([key, value]) => [key, String(value)]),
    )
    return request<Page<Product>>(`/stores/${encodeURIComponent(slug)}/products?${query}`, {
      signal,
    })
  },
}
