"""Unit tests for TrackTagData domain model and validation (TASK-001, TC-VAL-*, TC-SAN-*, TC-REG-*)."""
from dataclasses import FrozenInstanceError
import unittest

from cdripper.domain.models import AlbumMetadata, AlbumTagData, TrackTagData
from cdripper.domain.validation import (
    parse_and_validate_fractional_tag,
    sanitize_tag_string,
    validate_date_string,
)


class TestTrackTagData(unittest.TestCase):
    def test_immutability(self):
        """TC-META-004, TC-REG-003: TrackTagData is frozen and cannot be mutated."""
        tag = TrackTagData.create_default(track_number=1, total_tracks=10)
        with self.assertRaises(FrozenInstanceError):
            tag.title = "Modified"  # type: ignore

    def test_album_tag_data_immutability(self):
        """TC-REG-004: AlbumTagData is frozen and cannot be mutated."""
        album = AlbumTagData(album="Initial")
        with self.assertRaises(FrozenInstanceError):
            album.album = "Changed"  # type: ignore

    def test_property_formatting(self):
        """TC-RIP-001: Formats track and disc tag strings correctly."""
        tag = TrackTagData(
            track_number=2,
            total_tracks=12,
            disc_number=1,
            total_discs=2,
            title="Come Together",
            artist="The Beatles",
            album="Abbey Road",
            date="1969",
            genre="Rock",
            album_artist="The Beatles",
        )
        self.assertEqual(tag.track_tag_value, "2/12")
        self.assertEqual(tag.disc_tag_value, "1/2")
        self.assertEqual(tag.album_artist, "The Beatles")

    def test_album_artist_in_metadata_dict(self):
        """TC-AC005-01, FIND-001: album_artist is included in to_metadata_dict when present."""
        tag = TrackTagData(
            track_number=1,
            total_tracks=1,
            disc_number=1,
            total_discs=1,
            title="Song",
            artist="Soloist",
            album="Symphony",
            date="2026",
            genre="Classical",
            album_artist="Conductor & Orchestra",
        )
        d = tag.to_metadata_dict()
        self.assertEqual(d["album_artist"], "Conductor & Orchestra")
        self.assertEqual(d["artist"], "Soloist")

    def test_stripping_empty_tags(self):
        """TC-RIP-003, CHALLENGE-008: Empty or whitespace tags are stripped from metadata dict."""
        tag = TrackTagData(
            track_number=1,
            total_tracks=1,
            disc_number=1,
            total_discs=1,
            title="Song",
            artist="Artist",
            album="Album",
            date="   ",
            genre="",
            album_artist="   ",
        )
        d = tag.to_metadata_dict()
        self.assertIn("title", d)
        self.assertIn("artist", d)
        self.assertNotIn("date", d)
        self.assertNotIn("genre", d)
        self.assertNotIn("album_artist", d)

    def test_create_default_backward_compatibility(self):
        """TC-REG-002: create_default works with existing signature and provides empty album_artist."""
        tag = TrackTagData.create_default(track_number=3, total_tracks=10)
        self.assertEqual(tag.album_artist, "")
        self.assertEqual(tag.title, "Track 03")

    def test_create_default_whitespace_title_fallback(self):
        """FIND-005: Whitespace-only title falls back to 'Track {track_number:02d}'."""
        tag = TrackTagData.create_default(track_number=3, total_tracks=10, title="   ")
        self.assertEqual(tag.title, "Track 03")

        tag_none = TrackTagData.create_default(track_number=4, total_tracks=10, title=None)
        self.assertEqual(tag_none.title, "Track 04")

        tag_empty = TrackTagData.create_default(track_number=5, total_tracks=10, title="")
        self.assertEqual(tag_empty.title, "Track 05")


class TestValidation(unittest.TestCase):
    def test_sanitize_tag_string_control_chars_and_null(self):
        """TC-SAN-001, TC-SEC-002: Strips NULL bytes and replaces newlines/tabs with spaces."""
        raw = "Track\nTitle\r\nWith\tTabs\0andNull"
        sanitized = sanitize_tag_string(raw)
        self.assertNotIn("\0", sanitized)
        self.assertNotIn("\n", sanitized)
        self.assertNotIn("\r", sanitized)
        self.assertNotIn("\t", sanitized)
        self.assertEqual(sanitized, "Track Title With Tabs andNull")

    def test_sanitize_tag_string_max_length(self):
        """TC-SAN-002, TC-BND-009: Truncates long strings to max_length."""
        raw = "A" * 300
        sanitized = sanitize_tag_string(raw, max_length=256)
        self.assertEqual(len(sanitized), 256)

    def test_parse_fractional_tag_valid(self):
        self.assertEqual(parse_and_validate_fractional_tag("1/12"), (1, 12))
        self.assertEqual(parse_and_validate_fractional_tag("5"), (5, 0))

    def test_parse_fractional_tag_zero_or_negative(self):
        """TC-VAL-001, TC-VAL-002: Rejects zero and negative numbers."""
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("0")
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("-5")
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("abc")

    def test_parse_fractional_tag_zero_division(self):
        """TC-VAL-003: Rejects 1/0 without ZeroDivisionError."""
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("1/0")

    def test_parse_fractional_tag_upper_bounds(self):
        """TC-VAL-004: Rejects numbers > 999."""
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("1000")
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("1/1000")

    def test_parse_fractional_tag_exceeds_total(self):
        """TC-VAL-005: Rejects track number exceeding total."""
        with self.assertRaises(ValueError):
            parse_and_validate_fractional_tag("15/10")

    def test_validate_date_string(self):
        """TC-VAL-006: Validates 4-digit year format."""
        self.assertEqual(validate_date_string("2024"), "2024")
        self.assertEqual(validate_date_string(""), "")
        with self.assertRaises(ValueError):
            validate_date_string("abcd")
        with self.assertRaises(ValueError):
            validate_date_string("20")
        with self.assertRaises(ValueError):
            validate_date_string("99999")


if __name__ == "__main__":
    unittest.main()
