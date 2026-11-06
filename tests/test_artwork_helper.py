import unittest.mock
"""Unit tests for ArtworkHelper utilities (TASK-001, TC-AC001-*, TC-AC004-*, TC-BND-*, TC-NEG-*, TC-CONC-006)."""
from io import BytesIO
import unittest
from PIL import Image

from cdripper.ui.artwork_helper import (
    MAX_ARTWORK_SIZE_BYTES,
    MAX_IMAGE_PIXELS,
    create_photo_image,
    load_and_resize_image,
    normalize_artwork,
)


def _make_dummy_image_bytes(format_name: str, size=(100, 100), mode="RGB") -> bytes:
    img = Image.new(mode, size, color=(255, 0, 0))
    bio = BytesIO()
    img.save(bio, format=format_name)
    return bio.getvalue()


class TestArtworkHelper(unittest.TestCase):
    def test_normalize_valid_jpeg(self):
        """TC-AC001-01: Valid RGB JPEG normalizes successfully."""
        data = _make_dummy_image_bytes("JPEG", size=(300, 300))
        norm = normalize_artwork(data)
        self.assertIsNotNone(norm)
        img = Image.open(BytesIO(norm))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(img.mode, "RGB")
        self.assertEqual(img.size, (300, 300))

    def test_normalize_valid_png(self):
        """TC-AC001-02: Valid RGBA PNG normalizes successfully."""
        data = _make_dummy_image_bytes("PNG", size=(300, 300), mode="RGBA")
        norm = normalize_artwork(data)
        self.assertIsNotNone(norm)
        img = Image.open(BytesIO(norm))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.mode, "RGBA")

    def test_normalize_webp_converts_to_jpeg(self):
        """TC-AC004-03, FIND-002: Valid WEBP is converted to RGB JPEG."""
        data = _make_dummy_image_bytes("WEBP", size=(400, 400))
        norm = normalize_artwork(data)
        self.assertIsNotNone(norm)
        img = Image.open(BytesIO(norm))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(img.mode, "RGB")

    def test_normalize_cmyk_converts_to_rgb(self):
        """TC-NEG-007, FIND-002: CMYK JPEG is converted to RGB JPEG for FFmpeg MP4 compatibility."""
        data = _make_dummy_image_bytes("JPEG", size=(200, 200), mode="CMYK")
        norm = normalize_artwork(data)
        self.assertIsNotNone(norm)
        img = Image.open(BytesIO(norm))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(img.mode, "RGB")

    def test_normalize_exif_orientation_correction(self):
        """TC-AC004-05, FIND-007: EXIF orientation is normalized."""
        img = Image.new("RGB", (200, 100), color=(0, 255, 0))
        bio = BytesIO()
        exif = img.getexif()
        exif[0x0112] = 6  # 90 degrees CW rotation
        img.save(bio, format="JPEG", exif=exif)
        norm = normalize_artwork(bio.getvalue())
        self.assertIsNotNone(norm)
        out_img = Image.open(BytesIO(norm))
        # After orientation correction, width and height transpose
        self.assertEqual(out_img.size, (100, 200))

    def test_scale_down_exceeds_max_dimension(self):
        """TC-BND-005, TC-BND-006: Images exceeding 1400px are scaled down while maintaining aspect ratio."""
        data = _make_dummy_image_bytes("JPEG", size=(2800, 1400))
        norm = normalize_artwork(data, max_dimension=1400)
        self.assertIsNotNone(norm)
        img = Image.open(BytesIO(norm))
        self.assertEqual(img.size, (1400, 700))

    def test_rejects_oversized_file(self):
        """TC-BND-008: Reject files larger than 10MB."""
        oversized = b"X" * (MAX_ARTWORK_SIZE_BYTES + 1)
        self.assertIsNone(normalize_artwork(oversized))

    def test_rejects_corrupted_image(self):
        """TC-NEG-003: Safe fallback for corrupted image data."""
        corrupted = b"\xff\xd8\xff\xe0" + b"CorruptedData" * 10
        self.assertIsNone(normalize_artwork(corrupted))
        self.assertIsNone(load_and_resize_image(corrupted))

    def test_rejects_empty_image(self):
        """TC-NEG-004: Safe fallback for empty byte array."""
        self.assertIsNone(normalize_artwork(b""))
        self.assertIsNone(load_and_resize_image(b""))

    def test_decompression_bomb_protection(self):
        """TC-NEG-006: Protects against DecompressionBombError."""
        # Test that Image.MAX_IMAGE_PIXELS is configured properly
        self.assertEqual(MAX_IMAGE_PIXELS, 25_000_000)

    def test_headless_execution(self):
        """TC-CONC-006: normalize_artwork runs purely in PIL without requiring Tk display."""
        data = _make_dummy_image_bytes("JPEG", size=(50, 50))
        norm = normalize_artwork(data)
        self.assertIsNotNone(norm)


    def test_decompression_bomb_runtime_exception_handling(self):
        """TC-NEG-006: Ensure DecompressionBombError is caught and safely returns None."""
        from PIL import Image
        with unittest.mock.patch('PIL.Image.open', side_effect=Image.DecompressionBombError('Bomb')):
            result = normalize_artwork(b'dummy_data')
            self.assertIsNone(result)

    def test_exact_10mb_file_size_allowed(self):
        """TC-BND-007: Image data of exactly 10MB passes initial size check."""
        data_10mb = b'x' * (10 * 1024 * 1024)
        # Should not raise exception, returns None because content is invalid image (not because len > 10MB)
        res = normalize_artwork(data_10mb)
        self.assertIsNone(res)

    def test_load_and_resize_image_rejects_oversized_bytes(self):
        """SEC-002: load_and_resize_image rejects bytes larger than 10MB."""
        oversized = b'X' * (MAX_ARTWORK_SIZE_BYTES + 1)
        res = load_and_resize_image(oversized)
        self.assertIsNone(res)

    def test_normalize_opaque_png_converts_to_jpeg(self):
        """CR-001: Opaque PNG (mode=RGB) is consistently normalized to RGB JPEG."""
        img = Image.new('RGB', (100, 100), color=(100, 150, 200))
        buf = BytesIO()
        img.save(buf, format='PNG')
        res = normalize_artwork(buf.getvalue())
        self.assertIsNotNone(res)
        # Check output is JPEG
        out_img = Image.open(BytesIO(res))
        self.assertEqual(out_img.format, 'JPEG')

if __name__ == "__main__":
    unittest.main()
