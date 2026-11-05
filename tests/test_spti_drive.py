"""Unit tests for WindowsSPTICDDrive (TC-DRV-04, TC-DRV-05, TC-SPD-04, FIND-008, FIND-010, FIND-011)."""
import ctypes
import unittest
from unittest.mock import MagicMock, patch

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDDriveReadError,
)
from cdripper.hardware.spti_drive import (
    CDROM_TOC,
    ERROR_ACCESS_DENIED,
    ERROR_NO_MEDIA_IN_DRIVE,
    INVALID_HANDLE_VALUE,
    WindowsSPTICDDrive,
)


class TestSPTICDDrive(unittest.TestCase):
    def setUp(self):
        self.drive = WindowsSPTICDDrive()

    def test_open_invalid_drive_letter_format(self):
        """FIND-010 (SEC-004): 不正なドライブレター形式でValueErrorが送出されること"""
        with self.assertRaises(ValueError):
            self.drive.open("D:\\")
        with self.assertRaises(ValueError):
            self.drive.open("INVALID")
        with self.assertRaises(ValueError):
            self.drive.open("1:")

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.CreateFileW")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_access_denied_raises_custom_error(self, mock_err, mock_create):
        mock_create.return_value = INVALID_HANDLE_VALUE
        mock_err.return_value = ERROR_ACCESS_DENIED

        with self.assertRaises(CDDriveAccessDeniedError):
            self.drive.open("D:")

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_no_media_in_drive_raises_error(self, mock_err, mock_ioctl):
        self.drive._handle = 12345
        mock_ioctl.return_value = 0
        mock_err.return_value = ERROR_NO_MEDIA_IN_DRIVE

        with self.assertRaises(CDDriveNoMediaError):
            self.drive.read_toc()

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_read_toc_invalid_track_bounds(self, mock_ioctl):
        """FIND-011 (SEC-005): 不正なTOCトラック範囲でCDDriveReadErrorが送出されること"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            # FirstTrack 0 or > 99
            toc_ptr = out_b
            ctypes.cast(toc_ptr, ctypes.POINTER(CDROM_TOC)).contents.FirstTrack = 0
            ctypes.cast(toc_ptr, ctypes.POINTER(CDROM_TOC)).contents.LastTrack = 100
            return 1

        mock_ioctl.side_effect = side_effect
        with self.assertRaises(CDDriveReadError):
            self.drive.read_toc()

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_set_read_speed_failure_does_not_raise(self, mock_ioctl):
        self.drive._handle = 12345
        mock_ioctl.return_value = 0
        result = self.drive.set_read_speed(16)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
