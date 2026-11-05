"""Domain models for CD Ripping Application."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class BusType(str, Enum):
    """CD/DVD/BD Drive Bus Interface Type."""
    USB = "USB"
    SATA = "SATA"
    ATAPI = "ATAPI"
    VIRTUAL = "VIRTUAL"
    UNKNOWN = "UNKNOWN"


class EncodeFormat(str, Enum):
    """Audio Encoding Formats."""
    AAC_256K = "AAC (256kbps .m4a)"
    ALAC = "ALAC (Lossless .m4a)"
    MP3_320K = "MP3 (320kbps .mp3)"

    @property
    def extension(self) -> str:
        """Return the appropriate file extension."""
        if self in (EncodeFormat.AAC_256K, EncodeFormat.ALAC):
            return ".m4a"
        elif self == EncodeFormat.MP3_320K:
            return ".mp3"
        return ".m4a"


@dataclass(frozen=True)
class DriveInfo:
    """Optical drive information."""
    drive_letter: str            # e.g. "D:" or "V:"
    display_name: str            # e.g. "PIONEER BD-RW BDR-XD07 (USB)"
    bus_type: BusType
    is_ready: bool
    max_read_speed_x: int        # 0 if unknown
    recommended_speed_x: int     # Calculated safe read speed


@dataclass(frozen=True)
class TrackTOC:
    """Table of Contents entry for a single CD track."""
    track_number: int            # 1-based track index
    start_lba: int               # Logical Block Address start
    end_lba: int                 # Logical Block Address end
    sector_count: int            # Total sectors in this track
    duration_seconds: float      # duration in seconds (sectors / 75.0)
    is_audio: bool = True        # True for CD-DA audio tracks


@dataclass(frozen=True)
class DiscTOC:
    """Complete Table of Contents for an audio disc."""
    first_track: int
    last_track: int
    total_tracks: int
    total_duration_seconds: float
    tracks: List[TrackTOC]


@dataclass
class TrackMetadata:
    """Metadata for an individual audio track."""
    track_number: int
    track_title: str
    artist_name: str
    duration_millis: int
    disc_number: int = 1


@dataclass
class AlbumMetadata:
    """Complete album metadata retrieved from iTunes or mock."""
    collection_id: int
    album_name: str
    artist_name: str
    release_year: str
    genre: str
    total_tracks: int
    total_discs: int = 1
    artwork_url: Optional[str] = None
    artwork_data: Optional[bytes] = None
    tracks: List[TrackMetadata] = field(default_factory=list)


@dataclass
class RipConfig:
    """Configuration options for a ripping session."""
    output_dir: str
    format: EncodeFormat = EncodeFormat.AAC_256K
    selected_speed_x: int = 8
    speed_mode_auto: bool = True
    filename_template: str = "{track_num:02d} - {title}{ext}"


@dataclass
class RipProgress:
    """Real-time progress notification for UI update."""
    current_track: int
    total_tracks: int
    track_progress_percent: float
    overall_progress_percent: float
    current_speed_x: float
    status_text: str
    is_finished: bool = False
    error_message: Optional[str] = None