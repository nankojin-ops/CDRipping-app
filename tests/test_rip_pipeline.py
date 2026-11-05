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


if __name__ == "__main__":
    unittest.main()