"""Unit tests for AudioRipPipeline and sector boundary reading (FINDING-006, TC-RIP-01, TC-RIP-03)."""
import threading
import unittest

from cdripper.domain.models import TrackTOC
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.pipeline.rip_pipeline import read_track_sectors


class TestRipPipeline(unittest.TestCase):
    def test_sector_boundary_calculation(self):
        # 187 sectors: 75 + 75 + 37 (not a multiple of 75)
        track = TrackTOC(
            track_number=1,
            start_lba=100,
            end_lba=287,
            sector_count=187,
            duration_seconds=187 / 75.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)

        read_track_sectors(drive, track, on_chunk, batch_size=75)

        # Expected chunks: 75*2352, 75*2352, 37*2352
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 75 * 2352)
        self.assertEqual(len(chunks[1]), 75 * 2352)
        self.assertEqual(len(chunks[2]), 37 * 2352)

    def test_cancel_token_stops_reading(self):
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=1500,
            sector_count=1500,
            duration_seconds=20.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        token = threading.Event()
        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)
            token.set()  # Stop after 1 chunk

        read_track_sectors(drive, track, on_chunk, cancel_token=token, batch_size=75)
        self.assertEqual(len(chunks), 1)

    def test_read_track_sectors_default_batch_size_25(self):
        """TASK-006: batch_size省略時にデフォルト25セクタ単位でコールバックが呼ばれること"""
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=75,
            sector_count=75,
            duration_seconds=1.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)

        read_track_sectors(drive, track, on_chunk)  # batch_size omitted

        # 75 sectors with default batch_size=25 -> 3 chunks of 25 sectors
        self.assertEqual(len(chunks), 3)
        for chunk in chunks:
            self.assertEqual(len(chunk), 25 * 2352)



    def test_read_track_sectors_invalid_batch_size(self):
        """SEC-PIPE-001: batch_size <= 0 で ValueError が送出されること"""
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=75,
            sector_count=75,
            duration_seconds=1.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        with self.assertRaises(ValueError):
            read_track_sectors(drive, track, lambda chunk: None, batch_size=0)

        with self.assertRaises(ValueError):
            read_track_sectors(drive, track, lambda chunk: None, batch_size=-5)


if __name__ == "__main__":
    unittest.main()
