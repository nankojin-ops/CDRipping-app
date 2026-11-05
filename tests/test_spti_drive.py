"""Unit tests for WindowsSPTICDDrive and Win32 IOCTL handling (TC-DRV-04, TC-DRV-05, TC-SPD-04)."""
import unittest
from unittest.mock import MagicMock, patch

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
)
from cdripper.hardware.spti_drive import (
    ERROR_ACCESS_DENIED,
    ERROR_NO_MEDIA_IN_DRIVE,
    INVALID_HANDLE_VALUE,
    WindowsSPTICDDrive,
)


class TestSPTICDDrive(unittest.TestCase):
    def setUp(self):
        self.drive = WindowsSPTICDDrive()

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.CreateFileW")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_access_denied_raises_custom_error(self, mock_err, mock_create):
        """TC-DRV-05: アクセス拒否時の CDDriveAccessDeniedError 送出"""
        mock_create.return_value = INVALID_HANDLE_VALUE
        mock_err.return_value = ERROR_ACCESS_DENIED

        with self.assertRaises(CDDriveAccessDeniedError):
            self.drive.open("D:")

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_no_media_in_drive_raises_error(self, mock_err, mock_ioctl):
        """TC-DRV-04: ディスク未挿入時の CDDriveNoMediaError 送出"""
        self.drive._handle = 12345
        mock_ioctl.return_value = 0  # Failed
        mock_err.return_value = ERROR_NO_MEDIA_IN_DRIVE

        with self.assertRaises(CDDriveNoMediaError):
            self.drive.read_toc()

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_set_read_speed_failure_does_not_raise(self, mock_ioctl):
        """TC-SPD-04: ドライブがSET CD SPEEDコマンド非対応（失敗）時でも例外を投げずFalseを返すこと"""
        self.drive._handle = 12345
        mock_ioctl.return_value = 0  # コマンド失敗

        # 例外が発生せず、False が返ること
        result = self.drive.set_read_speed(16)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
