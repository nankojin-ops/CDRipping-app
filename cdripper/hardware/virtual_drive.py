"""Virtual CD Drive implementation for CI, testing, and fallback without physical drive."""
from __future__ import annotations

import math
import struct
from typing import List, Optional

from cdripper.domain.exceptions import CDDriveNoMediaError, CDDriveReadError
from cdripper.domain.models import BusType, DiscTOC, DriveInfo, TrackTOC
from cdripper.hardware.interface import ICDDrive

SECTOR_RAW_SIZE = 2352  # 2352 bytes per CD-DA sector (44.1kHz, 16-bit stereo)
SECTORS_PER_SECOND = 75


class VirtualCDDrive(ICDDrive):
    """In-memory virtual CD drive generating valid CD-DA PCM audio."""

    def __init__(self, track_durations: Optional[List[int]] = None, has_media: bool = True):
        """
        Initialize virtual drive.
        :param track_durations: List of durations in seconds for each track.
                                Defaults to [3, 4, 3] seconds (225, 300, 225 sectors).
        :param has_media: Whether a virtual disc is currently inserted.
        """
        self.is_open: bool = False
        self.selected_drive: Optional[str] = None
        self.has_media: bool = has_media
        self.current_speed_x: int = 24
        self.track_durations = track_durations or [3, 4, 3]
        self._error_lba: Optional[int] = None  # Inject error at this LBA for testing

    def inject_read_error_at_lba(self, lba: Optional[int]) -> None:
        """Inject simulated read error at specified LBA."""
        self._error_lba = lba

    def list_drives(self) -> List[DriveInfo]:
        """Return virtual optical drive info."""
        return [
            DriveInfo(
                drive_letter="V:",
                display_name="Virtual CD-ROM Drive (Test Mode)",
                bus_type=BusType.VIRTUAL,
                is_ready=self.has_media,
                max_read_speed_x=24,
                recommended_speed_x=8,
            )
        ]

    def open(self, drive_letter: str) -> bool:
        """Open the virtual drive."""
        self.selected_drive = drive_letter
        self.is_open = True
        return True

    def close(self) -> None:
        """Close the virtual drive."""
        self.is_open = False
        self.selected_drive = None

    def read_toc(self) -> DiscTOC:
        """Generate virtual DiscTOC."""
        if not self.has_media:
            raise CDDriveNoMediaError("No disc inserted in virtual drive.")

        tracks: List[TrackTOC] = []
        current_lba = 0
        total_seconds = 0.0

        for i, dur_sec in enumerate(self.track_durations, start=1):
            sector_cnt = int(dur_sec * SECTORS_PER_SECOND)
            track = TrackTOC(
                track_number=i,
                start_lba=current_lba,
                end_lba=current_lba + sector_cnt,
                sector_count=sector_cnt,
                duration_seconds=float(dur_sec),
                is_audio=True,
            )
            tracks.append(track)
            current_lba += sector_cnt
            total_seconds += float(dur_sec)

        return DiscTOC(
            first_track=1,
            last_track=len(tracks),
            total_tracks=len(tracks),
            total_duration_seconds=total_seconds,
            tracks=tracks,
        )

    def set_read_speed(self, speed_x: int) -> bool:
        """Set read speed."""
        self.current_speed_x = max(1, speed_x)
        return True

    def read_sectors_raw(self, start_lba: int, sector_count: int) -> bytes:
        """
        Generate raw CD-DA PCM sectors (44.1kHz, 16-bit signed stereo).
        2352 bytes per sector = 588 16-bit stereo samples (588 * 4 bytes).
        """
        if not self.has_media:
            raise CDDriveNoMediaError("No disc inserted in virtual drive.")

        if self._error_lba is not None:
            if start_lba <= self._error_lba < start_lba + sector_count:
                raise CDDriveReadError(f"Simulated read error at LBA {self._error_lba}")

        sample_rate = 44100
        frequency = 440.0
        samples_per_sector = 588  # 2352 / 4

        buffer = bytearray()
        for s in range(sector_count):
            lba = start_lba + s
            sample_offset_base = lba * samples_per_sector
            for i in range(samples_per_sector):
                t = (sample_offset_base + i) / sample_rate
                val = int(10000.0 * math.sin(2.0 * math.pi * frequency * t))
                buffer.extend(struct.pack("<hh", val, val))

        return bytes(buffer)