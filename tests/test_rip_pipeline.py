"""Unit tests for AudioRipPipeline and sector boundary reading (FINDING-006, TC-RIP-01, TC-RIP-03)."""
import threading
import unittest
from unittest.mock import MagicMock

from cdripper.domain.models import (
    AlbumMetadata,
    DiscTOC,
    RipConfig,
    TrackTagData,
    TrackTOC,
)
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.pipeline.rip_pipeline import AudioRipPipeline, read_track_sectors


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


    def test_rip_pipeline_embeds_album_artist_and_artwork(self):
        """TC-AC005-01, TC-AC005-02: Verifies album_artist and artwork are passed to encoder session."""
        mock_encoder = MagicMock()
        mock_encoder.start_encoding_session.return_value = MagicMock()

        pipeline = AudioRipPipeline(encoder=mock_encoder)
        drive = VirtualCDDrive(track_durations=[2])
        toc = DiscTOC(1, 1, 1, 2.0, [TrackTOC(1, 0, 150, 150, 2.0, True)])

        art_data = b"image_bytes_here"
        album = AlbumMetadata(
            collection_id=1,
            album_name="Test Album",
            artist_name="Test Artist",
            album_artist="Album Artist Name",
            release_year="2026",
            genre="Pop",
            total_tracks=1,
            artwork_data=art_data,
        )

        track_tags = {
            1: TrackTagData(
                track_number=1,
                total_tracks=1,
                disc_number=1,
                total_discs=1,
                title="Track 01",
                artist="Soloist",
                album_artist="Album Artist Name",
                album="Test Album",
                date="2026",
                genre="Pop",
            )
        }

        config = RipConfig(output_dir="test_out")
        cb = MagicMock()
        cancel_evt = MagicMock()
        cancel_evt.is_set.return_value = False

        pipeline.rip_disc(
            drive=drive,
            toc=toc,
            album=album,
            config=config,
            progress_callback=cb,
            cancel_event=cancel_evt,
            track_tags=track_tags,
        )

        mock_encoder.start_encoding_session.assert_called_once()
        call_kwargs = mock_encoder.start_encoding_session.call_args[1]
        self.assertEqual(call_kwargs["track_metadata"]["album_artist"], "Album Artist Name")
        self.assertEqual(call_kwargs["artwork_bytes"], art_data)


if __name__ == "__main__":
    unittest.main()
