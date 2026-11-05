"""Windows SCSI Pass-Through Interface (SPTI) and DeviceIoControl CD Drive Implementation."""
from __future__ import annotations

import ctypes
import os
import re
import sys
import threading
from ctypes import wintypes
from typing import List, Optional

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDDriveNotFoundError,
    CDDriveReadError,
)
from cdripper.domain.models import BusType, DiscTOC, DriveInfo, TrackTOC
from cdripper.hardware.interface import ICDDrive
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer

# Transfer length & sector constants
DEFAULT_FALLBACK_SECTORS = 25  # 約58.8KB (< 64KB USB境界)
MIN_TRANSFER_SECTORS = 1
MAX_TRANSFER_SECTORS_CAP = 75  # 1秒分 (176.4KB)
CDDA_SECTOR_SIZE = 2352
PAGE_SIZE = 4096

# Win32 Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

# IOCTL codes
IOCTL_CDROM_READ_TOC = 0x00024000
IOCTL_CDROM_RAW_READ = 0x0002403E
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x0004D014
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

# Win32 Error codes
ERROR_ACCESS_DENIED = 5
ERROR_NOT_READY = 21
ERROR_NO_MEDIA_IN_DRIVE = 1112

DRIVE_CDROM = 5

# Storage Query Property IDs
PropertyStandardQuery = 0
StorageDeviceProperty = 0
StorageAdapterProperty = 1

# Storage Bus Types
STORAGE_BUS_TYPE_ATAPI = 2
STORAGE_BUS_TYPE_ATA = 3
STORAGE_BUS_TYPE_USB = 7
STORAGE_BUS_TYPE_SATA = 11


# Setup 64-bit safe Win32 API signatures (FIND-005 / SEC-003)
if sys.platform == "win32":
    k32 = ctypes.windll.kernel32

    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]

    k32.CloseHandle.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]

    k32.DeviceIoControl.restype = wintypes.BOOL
    k32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]

    k32.GetLastError.restype = wintypes.DWORD
    k32.GetLastError.argtypes = []

    k32.GetDriveTypeW.restype = wintypes.UINT
    k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]

    k32.GetLogicalDrives.restype = wintypes.DWORD
    k32.GetLogicalDrives.argtypes = []


class TRACK_DATA(ctypes.Structure):
    _fields_ = [
        ("Reserved", ctypes.c_ubyte),
        ("ControlAdr", ctypes.c_ubyte),
        ("TrackNumber", ctypes.c_ubyte),
        ("Reserved1", ctypes.c_ubyte),
        ("Address", ctypes.c_ubyte * 4),
    ]


class CDROM_TOC(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("FirstTrack", ctypes.c_ubyte),
        ("LastTrack", ctypes.c_ubyte),
        ("TrackData", TRACK_DATA * 100),
    ]


class RAW_READ_INFO(ctypes.Structure):
    _fields_ = [
        ("DiskOffset", ctypes.c_int64),
        ("SectorCount", ctypes.c_ulong),
        ("TrackMode", ctypes.c_int),  # 0: CDDA
    ]


class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", ctypes.c_ulong),
        ("TimeOutValue", ctypes.c_ulong),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", ctypes.c_ulong),
        ("Cdb", ctypes.c_ubyte * 16),
    ]


class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", ctypes.c_int),
        ("QueryType", ctypes.c_int),
        ("AdditionalParameters", ctypes.c_ubyte * 1),
    ]


class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_ulong),
        ("Size", ctypes.c_ulong),
        ("DeviceType", ctypes.c_ubyte),
        ("DeviceTypeModifier", ctypes.c_ubyte),
        ("RemovableMedia", ctypes.c_ubyte),
        ("CommandQueueing", ctypes.c_ubyte),
        ("VendorIdOffset", ctypes.c_ulong),
        ("ProductIdOffset", ctypes.c_ulong),
        ("ProductRevisionOffset", ctypes.c_ulong),
        ("SerialNumberOffset", ctypes.c_ulong),
        ("BusType", ctypes.c_int),
        ("RawPropertiesLength", ctypes.c_ulong),
        ("RawDeviceProperties", ctypes.c_ubyte * 512),
    ]


class STORAGE_ADAPTER_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_ulong),
        ("Size", ctypes.c_ulong),
        ("MaximumTransferLength", ctypes.c_ulong),
        ("MaximumPhysicalPages", ctypes.c_ulong),
        ("AlignmentMask", ctypes.c_ulong),
        ("AdapterUsesPio", ctypes.c_ubyte),
        ("AdapterScansDown", ctypes.c_ubyte),
        ("CommandQueueing", ctypes.c_ubyte),
        ("AcceleratedTransfer", ctypes.c_ubyte),
        ("BusType", ctypes.c_ubyte),
        ("BusMajorVersion", ctypes.c_ushort),
        ("BusMinorVersion", ctypes.c_ushort),
        ("SrbType", ctypes.c_ubyte),
        ("AddressType", ctypes.c_ubyte),
    ]


class WindowsSPTICDDrive(ICDDrive):
    """Windows Optical Drive Reader using SPTI and Win32 IOCTLs."""

    def __init__(self):
        self._handle = None
        self._drive_letter: Optional[str] = None
        self._lock = threading.RLock()
        self._max_transfer_sectors: int = DEFAULT_FALLBACK_SECTORS
        self._supports_raw_read: bool = True

    def list_drives(self) -> List[DriveInfo]:
        """List all CD/DVD/BD optical drives on Windows system."""
        if sys.platform != "win32":
            return []

        kernel32 = ctypes.windll.kernel32
        drives: List[DriveInfo] = []
        bitmask = kernel32.GetLogicalDrives()

        for i in range(26):
            if bitmask & (1 << i):
                letter = f"{chr(65 + i)}:"
                root_path = f"{letter}\\"
                dtype = kernel32.GetDriveTypeW(root_path)
                if dtype == DRIVE_CDROM:
                    info = self._query_drive_info(letter)
                    drives.append(info)

        return drives

    def _query_drive_info(self, letter: str) -> DriveInfo:
        """Query drive details (display name, bus type, max speed) via Win32 IOCTL (FIND-008)."""
        bus_type = BusType.UNKNOWN
        display_name = f"CD/DVD Drive ({letter})"
        max_speed = 0

        handle = self._open_handle(letter, read_only=True)
        is_ready = False
        if handle and handle != INVALID_HANDLE_VALUE:
            try:
                # Query TOC to check readiness
                toc = CDROM_TOC()
                bytes_returned = wintypes.DWORD()
                ok = ctypes.windll.kernel32.DeviceIoControl(
                    handle,
                    IOCTL_CDROM_READ_TOC,
                    None,
                    0,
                    ctypes.byref(toc),
                    ctypes.sizeof(toc),
                    ctypes.byref(bytes_returned),
                    None,
                )
                if ok:
                    is_ready = True

                # FIND-008 (REV-006): Query Storage Device Descriptor for bus type
                query = STORAGE_PROPERTY_QUERY()
                query.PropertyId = StorageDeviceProperty
                query.QueryType = PropertyStandardQuery

                desc = STORAGE_DEVICE_DESCRIPTOR()
                desc_bytes = wintypes.DWORD()
                query_ok = ctypes.windll.kernel32.DeviceIoControl(
                    handle,
                    IOCTL_STORAGE_QUERY_PROPERTY,
                    ctypes.byref(query),
                    ctypes.sizeof(query),
                    ctypes.byref(desc),
                    ctypes.sizeof(desc),
                    ctypes.byref(desc_bytes),
                    None,
                )
                if query_ok:
                    raw_bus = desc.BusType
                    if raw_bus == STORAGE_BUS_TYPE_USB:
                        bus_type = BusType.USB
                    elif raw_bus == STORAGE_BUS_TYPE_SATA:
                        bus_type = BusType.SATA
                    elif raw_bus in (STORAGE_BUS_TYPE_ATAPI, STORAGE_BUS_TYPE_ATA):
                        bus_type = BusType.ATAPI

                    # Extract product / vendor string if available
                    raw_bytes = bytes(desc.RawDeviceProperties)
                    prod_offset = desc.ProductIdOffset
                    if prod_offset > 0 and prod_offset < len(raw_bytes):
                        end = raw_bytes.find(b"\x00", prod_offset)
                        if end != -1:
                            prod_str = raw_bytes[prod_offset:end].decode("ascii", errors="ignore").strip()
                            if prod_str:
                                display_name = f"{prod_str} ({letter})"
            except Exception:
                pass
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)

        temp_info = DriveInfo(
            drive_letter=letter,
            display_name=display_name,
            bus_type=bus_type,
            is_ready=is_ready,
            max_read_speed_x=max_speed,
            recommended_speed_x=0,
        )
        recommended = DriveSpeedOptimizer.calculate_recommended_speed(temp_info)
        return DriveInfo(
            drive_letter=letter,
            display_name=display_name,
            bus_type=bus_type,
            is_ready=is_ready,
            max_read_speed_x=max_speed,
            recommended_speed_x=recommended,
        )

    def _open_handle(self, drive_letter: str, read_only: bool = False):
        """Open Win32 file handle to \\\\.\\X: with 64-bit safe types."""
        if sys.platform != "win32":
            return None

        device_path = f"\\\\.\\{drive_letter.rstrip('\\')}"
        access = GENERIC_READ if read_only else (GENERIC_READ | GENERIC_WRITE)
        share = FILE_SHARE_READ | FILE_SHARE_WRITE

        handle = ctypes.windll.kernel32.CreateFileW(
            device_path,
            access,
            share,
            None,
            OPEN_EXISTING,
            0,
            None,
        )

        if handle == INVALID_HANDLE_VALUE and not read_only:
            err = ctypes.windll.kernel32.GetLastError()
            if err == ERROR_ACCESS_DENIED:
                handle = ctypes.windll.kernel32.CreateFileW(
                    device_path,
                    GENERIC_READ,
                    share,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )

        return handle

    def _query_adapter_transfer_limit(self) -> int:
        """Query storage adapter transfer limits via IOCTL_STORAGE_QUERY_PROPERTY (FIND-001, FIND-008)."""
        if not self._handle or self._handle == INVALID_HANDLE_VALUE or sys.platform != "win32":
            return DEFAULT_FALLBACK_SECTORS

        try:
            query = STORAGE_PROPERTY_QUERY()
            query.PropertyId = StorageAdapterProperty
            query.QueryType = PropertyStandardQuery

            desc = STORAGE_ADAPTER_DESCRIPTOR()
            bytes_returned = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                self._handle,
                IOCTL_STORAGE_QUERY_PROPERTY,
                ctypes.byref(query),
                ctypes.sizeof(query),
                ctypes.byref(desc),
                ctypes.sizeof(desc),
                ctypes.byref(bytes_returned),
                None,
            )

            # FIND-008: Verify returned size is at least sizeof(STORAGE_ADAPTER_DESCRIPTOR)
            if not ok or bytes_returned.value < ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR):
                return DEFAULT_FALLBACK_SECTORS

            max_bytes = desc.MaximumTransferLength
            # FIND-001: Consider MaximumPhysicalPages for scatter-gather limits
            if desc.MaximumPhysicalPages > 1:
                page_limit = (desc.MaximumPhysicalPages - 1) * PAGE_SIZE
                if page_limit > 0:
                    max_bytes = min(max_bytes, page_limit)

            if max_bytes < CDDA_SECTOR_SIZE:
                return DEFAULT_FALLBACK_SECTORS

            max_sectors = max_bytes // CDDA_SECTOR_SIZE
            return max(MIN_TRANSFER_SECTORS, min(MAX_TRANSFER_SECTORS_CAP, max_sectors))
        except Exception:
            return DEFAULT_FALLBACK_SECTORS

    def open(self, drive_letter: str) -> bool:
        """Open the target optical drive with input validation (FIND-010)."""
        # FIND-010 (SEC-004): Validate drive letter format (e.g. "D:")
        if not re.match(r"^[a-zA-Z]:$", drive_letter):
            raise ValueError(f"Invalid drive letter format: {drive_letter}")

        if sys.platform != "win32":
            raise CDDriveNotFoundError("SPTI drive is only supported on Windows.")

        with self._lock:
            self.close()
            handle = self._open_handle(drive_letter)
            if handle == INVALID_HANDLE_VALUE or handle is None:
                err = ctypes.windll.kernel32.GetLastError()
                if err == ERROR_ACCESS_DENIED:
                    raise CDDriveAccessDeniedError(
                        f"Access denied to drive {drive_letter}. Administrator privileges or UAC elevation may be required."
                    )
                raise CDDriveNotFoundError(f"Failed to open drive {drive_letter}. Error code: {err}")

            self._handle = handle
            self._drive_letter = drive_letter
            self._supports_raw_read = True
            self._max_transfer_sectors = self._query_adapter_transfer_limit()
            return True

    def close(self) -> None:
        """Close opened drive handle and reset adapter state (FIND-006, FIND-007)."""
        with self._lock:
            if self._handle and self._handle != INVALID_HANDLE_VALUE:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
            self._drive_letter = None
            self._max_transfer_sectors = DEFAULT_FALLBACK_SECTORS
            self._supports_raw_read = True

    def read_toc(self) -> DiscTOC:
        """Read CD-DA Table of Contents with track bound validation (FIND-011)."""
        with self._lock:
            if not self._handle or self._handle == INVALID_HANDLE_VALUE:
                raise CDDriveNotFoundError("Drive is not open.")

            toc = CDROM_TOC()
            bytes_ret = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                self._handle,
                IOCTL_CDROM_READ_TOC,
                None,
                0,
                ctypes.byref(toc),
                ctypes.sizeof(toc),
                ctypes.byref(bytes_ret),
                None,
            )

            if not ok:
                err = ctypes.windll.kernel32.GetLastError()
                if err in (ERROR_NOT_READY, ERROR_NO_MEDIA_IN_DRIVE):
                    raise CDDriveNoMediaError("No audio CD in drive.")
                if err == ERROR_ACCESS_DENIED:
                    raise CDDriveAccessDeniedError("Access denied reading TOC.")
                raise CDDriveReadError(f"Failed to read TOC. Win32 error: {err}")

            # FIND-011 (SEC-005): Validate TOC track boundaries (Red Book 1-99)
            if not (1 <= toc.FirstTrack <= toc.LastTrack <= 99):
                raise CDDriveReadError(
                    f"Invalid TOC track bounds: FirstTrack={toc.FirstTrack}, LastTrack={toc.LastTrack}"
                )

            tracks: List[TrackTOC] = []
            track_count = toc.LastTrack - toc.FirstTrack + 1

            def msf_to_lba(m: int, s: int, f: int) -> int:
                return (m * 60 + s) * 75 + f - 150

            for i in range(track_count):
                cur = toc.TrackData[i]
                nxt = toc.TrackData[i + 1]

                cur_lba = msf_to_lba(cur.Address[1], cur.Address[2], cur.Address[3])
                nxt_lba = msf_to_lba(nxt.Address[1], nxt.Address[2], nxt.Address[3])

                sector_count = max(0, nxt_lba - cur_lba)
                is_audio = (cur.ControlAdr & 0x04) == 0

                tracks.append(
                    TrackTOC(
                        track_number=cur.TrackNumber,
                        start_lba=cur_lba,
                        end_lba=nxt_lba,
                        sector_count=sector_count,
                        duration_seconds=sector_count / 75.0,
                        is_audio=is_audio,
                    )
                )

            leadout = toc.TrackData[track_count]
            leadout_lba = msf_to_lba(leadout.Address[1], leadout.Address[2], leadout.Address[3])
            first_lba = tracks[0].start_lba if tracks else 0
            total_sectors = max(0, leadout_lba - first_lba)

            return DiscTOC(
                first_track=toc.FirstTrack,
                last_track=toc.LastTrack,
                total_tracks=len(tracks),
                total_duration_seconds=total_sectors / 75.0,
                tracks=tracks,
            )

    def set_read_speed(self, speed_x: int) -> bool:
        """Issue MMC SET CD SPEED command (0xBB) via SCSI Pass-Through."""
        with self._lock:
            if not self._handle or self._handle == INVALID_HANDLE_VALUE:
                return False

            kbps = int(speed_x * 176.4)
            if speed_x == 0:
                kbps = 0xFFFF  # Max speed

            sptd = SCSI_PASS_THROUGH_DIRECT()
            sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
            sptd.CdbLength = 12
            sptd.DataIn = 0
            sptd.TimeOutValue = 5
            sptd.Cdb[0] = 0xBB  # SET CD SPEED
            sptd.Cdb[2] = (kbps >> 8) & 0xFF
            sptd.Cdb[3] = kbps & 0xFF
            sptd.Cdb[4] = 0xFF
            sptd.Cdb[5] = 0xFF

            bytes_ret = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                self._handle,
                IOCTL_SCSI_PASS_THROUGH_DIRECT,
                ctypes.byref(sptd),
                ctypes.sizeof(sptd),
                ctypes.byref(sptd),
                ctypes.sizeof(sptd),
                ctypes.byref(bytes_ret),
                None,
            )
            return bool(ok)

    def read_sectors_raw(self, start_lba: int, sector_count: int) -> bytes:
        """Read raw CD-DA sectors with transparent chunking and error fallback (FIND-003, FIND-005, FIND-006)."""
        if sector_count <= 0:
            return b""

        with self._lock:
            if not self._handle or self._handle == INVALID_HANDLE_VALUE:
                raise CDDriveNotFoundError("Drive is not open.")

            step = max(MIN_TRANSFER_SECTORS, self._max_transfer_sectors)
            if sector_count <= step:
                return self._read_sectors_chunk(start_lba, sector_count)

            chunks: List[bytes] = []
            remaining = sector_count
            current_lba = start_lba

            while remaining > 0:
                chunk_size = min(remaining, step)
                chunk_data = self._read_sectors_chunk(current_lba, chunk_size)
                chunks.append(chunk_data)
                current_lba += chunk_size
                remaining -= chunk_size

            return b"".join(chunks)

    def _read_sectors_chunk(self, start_lba: int, sector_count: int) -> bytes:
        """Read a single chunk of raw sectors with fallback and completeness check (FIND-002, FIND-004)."""
        buf_size = sector_count * CDDA_SECTOR_SIZE
        data: Optional[bytes] = None

        if self._supports_raw_read:
            buffer = ctypes.create_string_buffer(buf_size)
            raw_info = RAW_READ_INFO()
            raw_info.DiskOffset = start_lba * 2048
            raw_info.SectorCount = sector_count
            raw_info.TrackMode = 0  # CDDA

            bytes_ret = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                self._handle,
                IOCTL_CDROM_RAW_READ,
                ctypes.byref(raw_info),
                ctypes.sizeof(raw_info),
                buffer,
                buf_size,
                ctypes.byref(bytes_ret),
                None,
            )

            if ok:
                data = bytes(buffer.raw[:bytes_ret.value])
            else:
                err = ctypes.windll.kernel32.GetLastError()
                if err == ERROR_ACCESS_DENIED:
                    raise CDDriveAccessDeniedError("Access denied reading raw sectors.")
                # FIND-002: Any other error permanently disables RAW_READ and falls back to MMC READ CD
                self._supports_raw_read = False

        if data is None:
            data = self._read_cd_mmc(start_lba, sector_count)

        # FIND-004: Fail-fast verification of complete sector data
        expected_bytes = sector_count * CDDA_SECTOR_SIZE
        if len(data) != expected_bytes:
            raise CDDriveReadError(
                f"Incomplete sector read at LBA {start_lba}: expected {expected_bytes} bytes, got {len(data)} bytes"
            )

        return data

    def _read_cd_mmc(self, start_lba: int, sector_count: int) -> bytes:
        """Fallback raw read using SCSI command READ CD (0xBE)."""
        buf_size = sector_count * CDDA_SECTOR_SIZE
        buffer = ctypes.create_string_buffer(buf_size)

        sptd = SCSI_PASS_THROUGH_DIRECT()
        sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        sptd.CdbLength = 12
        sptd.DataIn = 1  # SCSI_IOCTL_DATA_IN
        sptd.DataTransferLength = buf_size
        sptd.TimeOutValue = 10
        sptd.DataBuffer = ctypes.cast(buffer, ctypes.c_void_p)

        sptd.Cdb[0] = 0xBE
        sptd.Cdb[1] = 0x04  # CD-DA
        sptd.Cdb[2] = (start_lba >> 24) & 0xFF
        sptd.Cdb[3] = (start_lba >> 16) & 0xFF
        sptd.Cdb[4] = (start_lba >> 8) & 0xFF
        sptd.Cdb[5] = start_lba & 0xFF
        sptd.Cdb[6] = (sector_count >> 16) & 0xFF
        sptd.Cdb[7] = (sector_count >> 8) & 0xFF
        sptd.Cdb[8] = sector_count & 0xFF
        sptd.Cdb[9] = 0xF8

        bytes_ret = wintypes.DWORD()
        ok = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            IOCTL_SCSI_PASS_THROUGH_DIRECT,
            ctypes.byref(sptd),
            ctypes.sizeof(sptd),
            ctypes.byref(sptd),
            ctypes.sizeof(sptd),
            ctypes.byref(bytes_ret),
            None,
        )

        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            raise CDDriveReadError(f"MMC READ CD failed. Win32 error: {err}")

        return bytes(buffer.raw[:sptd.DataTransferLength])
