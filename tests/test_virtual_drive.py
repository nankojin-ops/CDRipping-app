"""Unit tests for VirtualCDDrive (TC-MCK-01, TC-MCK-03, TC-MCK-04)."""
import unittest

from cdripper.domain.exceptions import CDDriveNoMediaError, CDDriveReadError
from cdripper.hardware.virtual_drive import VirtualCDDrive


class TestVirtualCDDrive(unittest.TestCase):
    def setUp(self):
        self.drive = VirtualCDDrive(track_durations=[2, 3])

    def test_list_drives(self):
        drives = self.drive.list_drives()
        self.assertEqual(len(drives), 1)
        self.assertEqual(drives[0].drive_letter, "V:")
        self.assertTrue(drives[0].is_ready)

    def test_read_toc_and_pcm_stream(self):
        self.drive.open("V:")
        toc = self.drive.read_toc()
        self.assertEqual(toc.total_tracks, 2)
        self.assertEqual(toc.tracks[0].track_number, 1)
        self.assertEqual(toc.tracks[0].duration_seconds, 2.0)
        self.assertEqual(toc.tracks[1].duration_seconds, 3.0)

        # 1 sector = 2352 bytes
        pcm_chunk = self.drive.read_sectors_raw(start_lba=0, sector_count=2)
        self.assertEqual(len(pcm_chunk), 2352 * 2)

    def test_no_media_exception(self):
        empty_drive = VirtualCDDrive(has_media=False)
        empty_drive.open("V:")
        with self.assertRaises(CDDriveNoMediaError):
            empty_drive.read_toc()
        with self.assertRaises(CDDriveNoMediaError):
            empty_drive.read_sectors_raw(0, 1)

    def test_injected_read_error(self):
        self.drive.open("V:")
        self.drive.inject_read_error_at_lba(50)
        # Reading LBA 0-10 is ok
        self.drive.read_sectors_raw(0, 10)
        # Reading range containing 50 throws error
        with self.assertRaises(CDDriveReadError):
            self.drive.read_sectors_raw(45, 10)


if __name__ == "__main__":
    unittest.main()