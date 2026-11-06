"""Helper utilities for safely decoding, normalizing, and rendering artwork images."""
from __future__ import annotations

from io import BytesIO
from typing import Optional, Tuple
from PIL import Image, ImageOps, ImageTk

MAX_ARTWORK_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_IMAGE_PIXELS = 25_000_000             # Decompression Bomb protection
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}


def normalize_artwork(image_bytes: bytes, max_dimension: int = 1400) -> Optional[bytes]:
    """
    Validate, fix EXIF orientation, and normalize artwork to RGB JPEG (or RGBA PNG).
    Guarantees compatibility with FFmpeg MP4 covr atom and prevents bloated rips.
    (FIND-002, FIND-007)
    """
    if not image_bytes or len(image_bytes) > MAX_ARTWORK_SIZE_BYTES:
        return None

    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        bio = BytesIO(image_bytes)
        img = Image.open(bio)
        img.verify()

        bio.seek(0)
        img = Image.open(bio)
        if img.format not in ALLOWED_IMAGE_FORMATS:
            return None

        # Fix EXIF orientation (FIND-007)
        img = ImageOps.exif_transpose(img)

        # Scale down if exceeds max_dimension
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            resample = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
            img = img.resize(new_size, resample=resample)

        out_buf = BytesIO()
        if "A" in img.mode:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img.save(out_buf, format="PNG", optimize=True)
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out_buf, format="JPEG", quality=90, optimize=True)

        return out_buf.getvalue()
    except Exception:
        return None


def load_and_resize_image(image_bytes: bytes, max_size: Tuple[int, int] = (150, 150)) -> Optional[Image.Image]:
    """Decode and thumbnail image for preview rendering."""
    # SEC-002: Input size defense in depth
    if not image_bytes or len(image_bytes) > MAX_ARTWORK_SIZE_BYTES:
        return None
    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        bio = BytesIO(image_bytes)
        img = Image.open(bio)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        resample = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
        img.thumbnail(max_size, resample=resample)
        return img
    except Exception:
        return None


def create_photo_image(image_bytes: bytes, max_size: Tuple[int, int] = (150, 150)) -> Optional[ImageTk.PhotoImage]:
    """Create Tkinter PhotoImage from image bytes safely."""
    pil_img = load_and_resize_image(image_bytes, max_size)
    if pil_img is None:
        return None
    try:
        return ImageTk.PhotoImage(pil_img)
    except Exception:
        return None
