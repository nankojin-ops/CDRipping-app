"""Unit tests for CDRipperPresenter event handling, threading, and SSOT track tags."""
import time
import unittest
from unittest.mock import MagicMock

from cdripper.domain.models import AlbumTagData, BusType, DiscTOC, DriveInfo, TrackTagData, TrackTOC
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.metadata.mock_provider import MockMetadataProvider
from cdripper.ui.presenter import CDRipperPresenter, PresenterEvent


class TestPresenter(unittest.TestCase):
    def setUp(self):
        self.drive = VirtualCDDrive(track_durations=[2, 2])
        self.meta = MockMetadataProvider()
        self.presenter = CDRipperPresenter(drive=self.drive, metadata_provider=self.meta)

    def test_scan_and_select_drive(self):
        """TC-DRV-01: ドライブ検出とTOC読み込み"""
        self.presenter.scan_drives()
        time.sleep(0.1)

        events = []
        while not self.presenter.event_queue.empty():
            events.append(self.presenter.event_queue.get_nowait())

        drive_events = [e for e in events if e[0] == PresenterEvent.DRIVES_LOADED]
        self.assertTrue(len(drive_events) > 0)

        self.presenter.select_drive("V:")
        time.sleep(0.1)

        toc_events = []
        while not self.presenter.event_queue.empty():
            item = self.presenter.event_queue.get_nowait()
            if item[0] == PresenterEvent.TOC_LOADED:
                toc_events.append(item)

        self.assertTrue(len(toc_events) > 0)
        self.assertEqual(toc_events[0][1].total_tracks, 2)
        self.assertEqual(len(self.presenter.track_tags), 2)
        self.assertFalse(self.presenter.track_tags[1].is_customized)

    def test_update_album_tags_batch_update_and_protection(self):
        """TC-AC003-01, TC-AC003-02: Propagates album tags while protecting track-specific data."""
        self.presenter.track_tags = {
            1: TrackTagData.create_default(1, 2, title="Song 1", artist="Soloist A", album="Old Album"),
            2: TrackTagData.create_default(2, 2, title="Song 2", artist="Soloist B", album="Old Album"),
        }

        album_data = AlbumTagData(
            disc_number=2,
            total_discs=3,
            album_artist="Various Artists",
            album="Masterpiece Collection",
            date="2026",
            genre="Classical",
            artwork_data=b"fake_cover_bytes",
        )

        self.presenter.update_album_tags(album_data)

        # Track 1 check
        t1 = self.presenter.track_tags[1]
        self.assertEqual(t1.title, "Song 1")  # Protected
        self.assertEqual(t1.artist, "Soloist A")  # Protected
        self.assertEqual(t1.album_artist, "Various Artists")  # Updated
        self.assertEqual(t1.album, "Masterpiece Collection")  # Updated
        self.assertEqual(t1.disc_number, 2)  # Updated
        self.assertEqual(t1.total_discs, 3)  # Updated
        self.assertEqual(t1.date, "2026")  # Updated
        self.assertEqual(t1.genre, "Classical")  # Updated

        # Track 2 check
        t2 = self.presenter.track_tags[2]
        self.assertEqual(t2.title, "Song 2")  # Protected
        self.assertEqual(t2.artist, "Soloist B")  # Protected
        self.assertEqual(t2.album_artist, "Various Artists")  # Updated

        # FIND-004: selected_disc synchronized
        self.assertEqual(self.presenter.selected_disc, 2)

        # current_album synthesized
        self.assertIsNotNone(self.presenter.current_album)
        self.assertEqual(self.presenter.current_album.album_name, "Masterpiece Collection")
        self.assertEqual(self.presenter.current_album.artwork_data, b"fake_cover_bytes")

    def test_update_album_tags_preserves_customized_flags(self):
        """TC-AC003-03, FIND-003: Does NOT blanket overwrite is_customized to True."""
        self.presenter.track_tags = {
            1: TrackTagData.create_default(1, 2, title="T1", is_customized=False),
            2: TrackTagData.create_default(2, 2, title="T2", is_customized=True),
        }

        album_data = AlbumTagData(album="New Album", album_artist="Band")
        self.presenter.update_album_tags(album_data)

        self.assertFalse(self.presenter.track_tags[1].is_customized)
        self.assertTrue(self.presenter.track_tags[2].is_customized)

    def test_update_album_tags_ripping_guard(self):
        """TC-CONC-001: update_album_tags blocked while ripping."""
        self.presenter.is_ripping = True
        album_data = AlbumTagData(album="New Album")
        self.presenter.update_album_tags(album_data)

        err_event = self.presenter.event_queue.get_nowait()
        self.assertEqual(err_event[0], PresenterEvent.ERROR)

    def test_track_tags_ssot_and_sync(self):
        """TC-SSOT-001, TC-SSOT-002: SSOT updates and propagates to uncustomized tracks."""
        self.presenter.track_tags = {
            1: TrackTagData.create_default(1, 2, title="T1", artist="Old Artist", album="Old Album", is_customized=True),
            2: TrackTagData.create_default(2, 2, title="T2", artist="Old Artist", album="Old Album", is_customized=False),
        }
        self.assertTrue(self.presenter.has_customized_tracks())

        self.presenter.sync_album_artist_to_uncustomized(album="New Album", artist="New Artist")

        self.assertEqual(self.presenter.track_tags[1].artist, "Old Artist")
        self.assertEqual(self.presenter.track_tags[1].album, "Old Album")
        self.assertEqual(self.presenter.track_tags[2].artist, "New Artist")
        self.assertEqual(self.presenter.track_tags[2].album, "New Album")

    def test_is_ripping_guard(self):
        """TC-STATE-001, CHALLENGE-002: Prevents drive scan, selection, or duplicate rip while ripping."""
        self.presenter.is_ripping = True

        self.presenter.scan_drives()
        err_event = self.presenter.event_queue.get_nowait()
        self.assertEqual(err_event[0], PresenterEvent.ERROR)

        self.presenter.select_drive("V:")
        err_event2 = self.presenter.event_queue.get_nowait()
        self.assertEqual(err_event2[0], PresenterEvent.ERROR)


if __name__ == "__main__":
    unittest.main()
