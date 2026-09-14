import io

from PIL import Image, UnidentifiedImageError

from app.services.errors import InvalidImageError

# Claude downsamples anything larger; keeping images modest keeps requests fast.
MAX_EDGE = 1568
# Embedding models see a few hundred pixels at most; smaller payloads embed faster.
EMBED_EDGE = 512
# Pad detected boxes so the crop keeps the item's outline (soles, straps, handles).
CROP_PADDING = 0.08
# A box covering nearly the whole frame is a product shot already; cropping adds nothing.
MAX_USEFUL_BOX_AREA = 0.85
MIN_BOX_EDGE = 0.05


def normalize_image(data: bytes, max_edge: int = MAX_EDGE, quality: int = 88) -> bytes:
    """Validate arbitrary image bytes and re-encode as an RGB JPEG.

    Handles formats Claude doesn't accept (e.g. AVIF), bounds the size, and drops
    metadata such as EXIF location from user uploads.
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if getattr(image, "n_frames", 1) > 1:
                image.seek(0)
            return _encode(_to_rgb(image), max_edge, quality)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("That file isn't an image we can read.") from exc


def crop_to_box(jpeg: bytes, box: list[int] | None) -> bytes:
    """Crop to the primary item's bounding box ([ymin, xmin, ymax, xmax], 0-1000 scale).

    Isolating the item from background, people and other products is the first stage of
    industry visual search (detect, crop, then embed). Invalid or near-full-frame boxes
    return the image unchanged.
    """
    if not box or len(box) != 4:
        return jpeg
    ymin, xmin, ymax, xmax = (min(max(v, 0), 1000) / 1000 for v in box)
    height, width = ymax - ymin, xmax - xmin
    if height < MIN_BOX_EDGE or width < MIN_BOX_EDGE or height * width > MAX_USEFUL_BOX_AREA:
        return jpeg
    with Image.open(io.BytesIO(jpeg)) as image:
        image.load()
        w, h = image.size
        left = max(0.0, xmin - width * CROP_PADDING) * w
        top = max(0.0, ymin - height * CROP_PADDING) * h
        right = min(1.0, xmax + width * CROP_PADDING) * w
        bottom = min(1.0, ymax + height * CROP_PADDING) * h
        cropped = image.crop((round(left), round(top), round(right), round(bottom)))
        return _encode(_to_rgb(cropped), MAX_EDGE, 90)


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def _encode(image: Image.Image, max_edge: int, quality: int) -> bytes:
    image.thumbnail((max_edge, max_edge))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()
