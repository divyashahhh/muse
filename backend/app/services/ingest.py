"""Turn an upload or a product link into an analysed Item."""

from app.models import Item, ItemSource
from app.services.ai import ItemAnalysis, ProductAI
from app.services.embeddings import Vector, VisualSimilarity
from app.services.errors import FetchError
from app.services.fetch import fetch
from app.services.imaging import crop_to_box, normalize_image
from app.services.product_page import parse_product_page
from app.services.storage import ImageStorage

MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024


async def item_from_upload(
    data: bytes, storage: ImageStorage, ai: ProductAI, vision: VisualSimilarity | None = None
) -> Item:
    image = normalize_image(data)
    stored = await storage.save_jpeg(image)
    analysis = await ai.analyze(image, page=None)
    return Item(
        source=ItemSource.UPLOAD,
        image_key=stored.key,
        image_url=stored.url,
        analysis=analysis.model_dump(mode="json"),
        image_embedding=await reference_embedding(image, analysis, vision),
    )


async def reference_embedding(
    image_jpeg: bytes, analysis: ItemAnalysis, vision: VisualSimilarity | None
) -> Vector | None:
    """Embed the item cropped to its detected bounding box (detect -> crop -> embed)."""
    if vision is None:
        return None
    return await vision.reference(crop_to_box(image_jpeg, analysis.subject_box))


async def item_from_url(
    url: str, storage: ImageStorage, ai: ProductAI, vision: VisualSimilarity | None = None
) -> Item:
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
        title=page.title if page else None,
        brand=(page.brand if page else None) or analysis.brand,
        retailer=page.retailer if page else None,
        price=page.price if page else None,
        currency=page.currency if page else None,
        identifiers=page.identifiers if page else {},
        analysis=analysis.model_dump(mode="json"),
        image_embedding=await reference_embedding(image, analysis, vision),
    )
