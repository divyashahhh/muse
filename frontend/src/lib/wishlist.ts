import type { Item, RecentItem, WishlistInput, WishlistItem } from './api'

/** Muse's own page for a searched item, used as the saved link when there's no retailer page. */
export function itemPageUrl(itemId: string): string {
  return `${window.location.origin}/items/${itemId}`
}

/** A searched item (from Recents or its item page) as a wishlist entry. */
export function wishlistInputForItem(item: Item | RecentItem): WishlistInput {
  const productName = 'analysis' in item ? item.analysis.product_name : item.product_name
  return {
    item_id: item.id,
    title: item.title ?? productName,
    // Photo searches have no product page, so they link back to Muse.
    url: item.source_url ?? itemPageUrl(item.id),
    retailer: item.retailer,
    image_url: item.image_url,
    price: item.price,
    currency: item.currency,
  }
}

/** True when a saved entry links to a Muse item page rather than a retailer. */
export function linksToMuse(saved: Pick<WishlistItem, 'url'>): boolean {
  return saved.url.startsWith(`${window.location.origin}/items/`)
}
