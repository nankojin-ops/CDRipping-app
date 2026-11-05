"""Unit tests for CDRipperPresenter event handling and threading (TC-DRV-01 - TC-DRV-03)."""
import time
import unittest
from unittest.mock import MagicMock

from cdripper.domain.models import BusType, DiscTOC, DriveInfo, TrackTOC
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

    def test_zero_drives_handling(self):
        """TC-DRV-03: 光学ドライブが0台のとき、クラッシュせず適切に扱われること"""
        mock_drive = MagicMock()
        mock_drive.list_drives.return_value = []
        presenter = CDRipperPresenter(drive=mock_drive, metadata_provider=self.meta)

        presenter.scan_drives()
        time.sleep(0.1)

        events = []
        while not presenter.event_queue.empty():
            events.append(presenter.event_queue.get_nowait())

        drive_loaded = [e for e in events if e[0] == PresenterEvent.DRIVES_LOADED]
        self.assertEqual(len(drive_loaded), 1)
        self.assertEqual(drive_loaded[0][1], [])

    def test_multiple_drives_selection(self):
        """TC-DRV-02: 複数ドライブが存在する状況での選択切り替え動作"""
        mock_drive = MagicMock()
        drive_d = DriveInfo("D:", "Internal BD Drive", BusType.SATA, True, 48, 16)
        drive_e = DriveInfo("E:", "External USB Drive", BusType.USB, True, 24, 8)
        mock_drive.list_drives.return_value = [drive_d, drive_e]
        mock_drive.read_toc.return_value = DiscTOC(1, 1, 1, 10.0, [TrackTOC(1, 0, 750, 750, 10.0, True)])

        presenter = CDRipperPresenter(drive=mock_drive, metadata_provider=self.meta)
        presenter.scan_drives()
        time.sleep(0.1)

        self.assertEqual(len(presenter.current_drives), 2)

        # ドライブEを選択
        presenter.select_drive("E:")
        time.sleep(0.1)

        self.assertIsNotNone(presenter.selected_drive)
        self.assertEqual(presenter.selected_drive.drive_letter, "E:")
        mock_drive.open.assert_called_with("E:")


if __name__ == "__main__":
    unittest.main()
