"""Unit tests for domain models and exceptions."""
import unittest
from dataclasses import FrozenInstanceError

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDDriveNotFoundError,
    CDRipperError,
    EncodingError,
    FFmpegNotFoundError,
    MetadataError,
)
from cdripper.domain.models import (
    AlbumMetadata,
    BusType,
    DiscTOC,
    DriveInfo,
    EncodeFormat,
    RipConfig,
    RipProgress,
    TrackMetadata,
    TrackTOC,
)


class TestDomainModels(unittest.TestCase):
    def test_bus_type_and_encode_format(self):
        self.assertEqual(BusType.USB.value, "USB")
        self.assertEqual(BusType.SATA.value, "SATA")
        self.assertEqual(EncodeFormat.AAC_256K.extension, ".m4a")
        self.assertEqual(EncodeFormat.ALAC.extension, ".m4a")
        self.assertEqual(EncodeFormat.MP3_320K.extension, ".mp3")

    def test_drive_info_immutability(self):
        info = DriveInfo(
            drive_letter="D:",
            display_name="Pioneer Drive",
            bus_type=BusType.USB,
            is_ready=True,
            max_read_speed_x=24,
            recommended_speed_x=8,
        )
        self.assertEqual(info.drive_letter, "D:")
        with self.assertRaises(FrozenInstanceError):
            info.drive_letter = "E:"

    def test_disc_toc_immutability(self):
        track1 = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=150,
            sector_count=150,
            duration_seconds=2.0,
            is_audio=True,
        )
        disc = DiscTOC(
            first_track=1,
            last_track=1,
            total_tracks=1,
            total_duration_seconds=2.0,
            tracks=[track1],
        )
        self.assertEqual(len(disc.tracks), 1)
        with self.assertRaises(FrozenInstanceError):
            disc.total_tracks = 2

    def test_exceptions_hierarchy(self):
        self.assertTrue(issubclass(CDDriveAccessDeniedError, CDRipperError))
        self.assertTrue(issubclass(CDDriveNoMediaError, CDRipperError))
        self.assertTrue(issubclass(FFmpegNotFoundError, EncodingError))
        self.assertTrue(issubclass(MetadataError, CDRipperError))


if __name__ == "__main__":
    unittest.main()