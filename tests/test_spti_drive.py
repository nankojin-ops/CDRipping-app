"""Unit tests for WindowsSPTICDDrive (TC-DRV-04, TC-DRV-05, TC-SPD-04, FIND-001 ~ FIND-011)."""
import ctypes
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDDriveNotFoundError,
    CDDriveReadError,
)
from cdripper.hardware.spti_drive import (
    CDROM_TOC,
    ERROR_ACCESS_DENIED,
    ERROR_NO_MEDIA_IN_DRIVE,
    INVALID_HANDLE_VALUE,
    IOCTL_CDROM_RAW_READ,
    IOCTL_SCSI_PASS_THROUGH_DIRECT,
    SCSI_PASS_THROUGH_DIRECT,
    STORAGE_ADAPTER_DESCRIPTOR,
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

    # ---------------------------------------------------------
    # cd-ripping-app-002: TASK-005 拡充テストケース
    # ---------------------------------------------------------

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_normal(self, mock_ioctl):
        """TASK-005 (1): MaximumTransferLength=131072, MaximumPhysicalPages=33で55セクタが返ること"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            desc_ptr = ctypes.cast(out_b, ctypes.POINTER(STORAGE_ADAPTER_DESCRIPTOR))
            desc_ptr.contents.MaximumTransferLength = 131072
            desc_ptr.contents.MaximumPhysicalPages = 33  # (33-1)*4096 = 131072
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 55)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_64k(self, mock_ioctl):
        """TC-PROP-002: MaximumTransferLength=65536で27セクタが返ること"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            desc_ptr = ctypes.cast(out_b, ctypes.POINTER(STORAGE_ADAPTER_DESCRIPTOR))
            desc_ptr.contents.MaximumTransferLength = 65536
            desc_ptr.contents.MaximumPhysicalPages = 0
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 27)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_cap_at_75(self, mock_ioctl):
        """TC-PROP-006: MaximumTransferLength=1MBで75セクタにキャップされること"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            desc_ptr = ctypes.cast(out_b, ctypes.POINTER(STORAGE_ADAPTER_DESCRIPTOR))
            desc_ptr.contents.MaximumTransferLength = 1048576
            desc_ptr.contents.MaximumPhysicalPages = 0
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 75)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_under_one_sector(self, mock_ioctl):
        """TC-PROP-007: 2000バイト(1セクタ未満)で既定値25セクタにフォールバックすること"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            desc_ptr = ctypes.cast(out_b, ctypes.POINTER(STORAGE_ADAPTER_DESCRIPTOR))
            desc_ptr.contents.MaximumTransferLength = 2000
            desc_ptr.contents.MaximumPhysicalPages = 0
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 25)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_page_bound(self, mock_ioctl):
        """TASK-005 (2): MaximumPhysicalPages=16でページ制限 (16-1)*4096=61440バイト=26セクタに制限されること (FIND-001)"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            desc_ptr = ctypes.cast(out_b, ctypes.POINTER(STORAGE_ADAPTER_DESCRIPTOR))
            desc_ptr.contents.MaximumTransferLength = 131072
            desc_ptr.contents.MaximumPhysicalPages = 16  # (16-1)*4096 = 61440
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 26)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_failure_fallback(self, mock_ioctl):
        """TASK-005 (3): DeviceIoControl失敗時に既定値25セクタが返ること"""
        self.drive._handle = 12345
        mock_ioctl.return_value = 0
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 25)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_query_adapter_transfer_limit_short_descriptor(self, mock_ioctl):
        """TASK-005 (4): 返却バイト数がsizeof未満のときに既定値25セクタが返ること (FIND-008)"""
        self.drive._handle = 12345

        def side_effect(h, ioctl, in_b, in_s, out_b, out_s, ret, ov):
            ret_ptr = ctypes.cast(ret, ctypes.POINTER(ctypes.c_ulong))
            ret_ptr.contents.value = ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR) - 1
            return 1

        mock_ioctl.side_effect = side_effect
        limit = self.drive._query_adapter_transfer_limit()
        self.assertEqual(limit, 25)

    def test_read_sectors_raw_zero_or_negative(self):
        """TASK-005 (5): sector_count <= 0 で即時空バイトが返ること"""
        self.drive._handle = 12345
        self.assertEqual(self.drive.read_sectors_raw(0, 0), b"")
        self.assertEqual(self.drive.read_sectors_raw(0, -5), b"")

    def test_read_sectors_raw_not_open_raises(self):
        """未オープン時にCDDriveNotFoundErrorが送出されること"""
        self.drive._handle = None
        with self.assertRaises(CDDriveNotFoundError):
            self.drive.read_sectors_raw(0, 10)

    def test_read_sectors_raw_transparent_chunking(self):
        """TASK-005 (6): _max_transfer_sectors=25で75セクタ要求時、25セクタずつ3回呼ばれ結合されること (AC-002, FIND-005)"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 25

        calls = []

        def mock_read_chunk(start_lba, sector_count):
            calls.append((start_lba, sector_count))
            return b"X" * (sector_count * 2352)

        self.drive._read_sectors_chunk = mock_read_chunk
        result = self.drive.read_sectors_raw(100, 75)

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls, [(100, 25), (125, 25), (150, 25)])
        self.assertEqual(len(result), 75 * 2352)
        self.assertEqual(result, b"X" * (75 * 2352))

    def test_read_sectors_raw_remainder_chunking(self):
        """TC-CHUNK-004: 60セクタ要求時に25+25+10で分割されること"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 25
        calls = []

        def mock_read_chunk(start_lba, sector_count):
            calls.append((start_lba, sector_count))
            return b"A" * (sector_count * 2352)

        self.drive._read_sectors_chunk = mock_read_chunk
        res = self.drive.read_sectors_raw(10, 60)
        self.assertEqual(calls, [(10, 25), (35, 25), (60, 10)])
        self.assertEqual(len(res), 60 * 2352)

    def test_read_sectors_raw_abort_on_chunk_failure(self):
        """TC-CHUNK-011: 途中チャンク失敗時に後続チャンクが実行されず即時送出されること"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 25
        calls = []

        def mock_read_chunk(start_lba, sector_count):
            calls.append((start_lba, sector_count))
            if start_lba == 25:
                raise CDDriveReadError("Read failure at chunk 2")
            return b"B" * (sector_count * 2352)

        self.drive._read_sectors_chunk = mock_read_chunk
        with self.assertRaises(CDDriveReadError):
            self.drive.read_sectors_raw(0, 75)
        self.assertEqual(len(calls), 2)  # chunk 1 and 2, but not chunk 3

    def test_read_sectors_raw_infinite_loop_prevention(self):
        """TASK-005 (7): _max_transfer_sectors=0でもstep>=1で無限ループにならず終了すること (FIND-003)"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 0

        calls = []

        def mock_read_chunk(start_lba, sector_count):
            calls.append((start_lba, sector_count))
            return b"Y" * (sector_count * 2352)

        self.drive._read_sectors_chunk = mock_read_chunk
        result = self.drive.read_sectors_raw(0, 3)

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls, [(0, 1), (1, 1), (2, 1)])
        self.assertEqual(len(result), 3 * 2352)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_raw_read_fallback_on_any_error(self, mock_err, mock_ioctl):
        """TASK-005 (8): IOCTL_CDROM_RAW_READエラー時にMMC READ CDへフォールバックし_supports_raw_read=Falseになること (FIND-002)"""
        self.drive._handle = 12345
        self.drive._supports_raw_read = True

        def ioctl_side_effect(h, code, in_b, in_s, out_b, out_s, ret, ov):
            if code == IOCTL_CDROM_RAW_READ:
                mock_err.return_value = 1  # ERROR_INVALID_FUNCTION
                return 0
            elif code == IOCTL_SCSI_PASS_THROUGH_DIRECT:
                return 1
            return 0

        mock_ioctl.side_effect = ioctl_side_effect
        data = self.drive._read_sectors_chunk(0, 1)

        self.assertFalse(self.drive._supports_raw_read)
        self.assertEqual(len(data), 2352)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_raw_read_access_denied_raises_immediately(self, mock_err, mock_ioctl):
        """TC-IO-005: ERROR_ACCESS_DENIED時はMMCへフォールバックせず即座に例外送出すること"""
        self.drive._handle = 12345
        self.drive._supports_raw_read = True

        def ioctl_side_effect(h, code, in_b, in_s, out_b, out_s, ret, ov):
            if code == IOCTL_CDROM_RAW_READ:
                mock_err.return_value = ERROR_ACCESS_DENIED
                return 0
            return 1

        mock_ioctl.side_effect = ioctl_side_effect
        with self.assertRaises(CDDriveAccessDeniedError):
            self.drive._read_sectors_chunk(0, 1)
        self.assertTrue(self.drive._supports_raw_read)

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_read_sectors_chunk_incomplete_data_raises(self, mock_ioctl):
        """TASK-005 (9): ショートリード時にCDDriveReadErrorが送出されること (FIND-004)"""
        self.drive._handle = 12345
        self.drive._supports_raw_read = False  # Use MMC

        def ioctl_side_effect(h, code, in_b, in_s, out_b, out_s, ret, ov):
            sptd_ptr = ctypes.cast(in_b, ctypes.POINTER(SCSI_PASS_THROUGH_DIRECT))
            sptd_ptr.contents.DataTransferLength = 1000  # < 2352
            return 1

        mock_ioctl.side_effect = ioctl_side_effect
        with self.assertRaises(CDDriveReadError):
            self.drive._read_sectors_chunk(0, 1)

    def test_close_resets_state(self):
        """TASK-005 (10): close()後に_max_transfer_sectorsと_supports_raw_readが初期化されること (FIND-007)"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 55
        self.drive._supports_raw_read = False

        with patch("ctypes.windll.kernel32.CloseHandle"):
            self.drive.close()

        self.assertEqual(self.drive._max_transfer_sectors, 25)
        self.assertTrue(self.drive._supports_raw_read)
        self.assertIsNone(self.drive._handle)

    def test_concurrent_read_sectors_raw(self):
        """TC-CONC-001: 複数スレッド並行アクセス時にRLockで保護され正常に完了すること"""
        self.drive._handle = 12345
        self.drive._max_transfer_sectors = 25

        def mock_read_chunk(start_lba, sector_count):
            return bytes([start_lba % 256]) * (sector_count * 2352)

        self.drive._read_sectors_chunk = mock_read_chunk

        def worker(lba):
            return self.drive.read_sectors_raw(lba, 50)

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(worker, lba) for lba in [0, 50, 100, 150]]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(len(r), 50 * 2352)


if __name__ == "__main__":
    unittest.main()
