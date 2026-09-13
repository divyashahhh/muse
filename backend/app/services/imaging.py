import io

from PIL import Image, UnidentifiedImageError

from app.services.errors import InvalidImageError

# Claude downsamples anything larger; keeping images modest keeps requests fast.
MAX_EDGE = 1568


def normalize_image(data: bytes) -> bytes:
    """Validate arbitrary image bytes and re-encode as an RGB JPEG.

    Handles formats Claude doesn't accept (e.g. AVIF), bounds the size, and drops
    metadata such as EXIF location from user uploads.
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if getattr(image, "n_frames", 1) > 1:
                image.seek(0)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=88, optimize=True)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("That file isn't an image we can read.") from exc
