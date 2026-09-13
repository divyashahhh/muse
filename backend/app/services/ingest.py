"""Turn an upload or a product link into an analysed Item."""

from app.models import Item, ItemSource
from app.services.ai import ProductAI
from app.services.errors import FetchError
from app.services.fetch import fetch
from app.services.imaging import normalize_image
from app.services.product_page import parse_product_page
from app.services.storage import ImageStorage

MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024


async def item_from_upload(data: bytes, storage: ImageStorage, ai: ProductAI) -> Item:
    image = normalize_image(data)
    stored = await storage.save_jpeg(image)
    analysis = await ai.analyze(image, page=None)
    return Item(
        source=ItemSource.UPLOAD,
        image_key=stored.key,
        image_url=stored.url,
        search_image_url=stored.url if stored.internet_reachable else None,
        analysis=analysis.model_dump(mode="json"),
    )


async def item_from_url(url: str, storage: ImageStorage, ai: ProductAI) -> Item:
    resource = await fetch(
        url, max_bytes=MAX_PAGE_BYTES, accept="text/html,image/*;q=0.9,*/*;q=0.5"
    )

    if resource.content_type.startswith("image/"):
        page = None
        image_url, image_bytes = resource.url, resource.body
    else:
        page = parse_product_page(resource.body, resource.url)
        if not page.image_url:
            raise FetchError(
                "Couldn't find a product image on that page. Try uploading a photo of the item."
            )
        image_url = page.image_url
        image_bytes = (await fetch(image_url, max_bytes=MAX_IMAGE_BYTES, accept="image/*")).body

    image = normalize_image(image_bytes)
    stored = await storage.save_jpeg(image)
    analysis = await ai.analyze(image, page=page)
    return Item(
        source=ItemSource.URL,
        source_url=resource.url,
        image_key=stored.key,
        image_url=stored.url,
        # The retailer's own image is public, so Lens can use it even without cloud storage.
        search_image_url=image_url,
        title=page.title if page else None,
        brand=(page.brand if page else None) or analysis.brand,
        retailer=page.retailer if page else None,
        price=page.price if page else None,
        currency=page.currency if page else None,
        analysis=analysis.model_dump(mode="json"),
    )
