"""Domain models for CD Ripping Application."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


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
    album_artist: str = ""
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


@dataclass(frozen=True)
class AlbumTagData:
    """
    Immutable data object for album-level metadata and artwork.
    Guarantees thread-safe SSOT propagation to all disc tracks.
    (TASK-001, AC-002, AC-003)
    """
    disc_number: int = 1
    total_discs: int = 1
    album_artist: str = ""
    album: str = ""
    date: str = ""
    genre: str = ""
    artwork_data: Optional[bytes] = None


@dataclass(frozen=True)
class TrackTagData:
    """
    Immutable tag metadata for an individual audio track.
    guarantees mathematical thread-safety across UI and background worker threads.
    (CHALLENGE-001, CHALLENGE-007, AC-001, FIND-001)
    """
    track_number: int            # 1-based track index (Strictly int for filename template)
    total_tracks: int            # Total tracks count on disc
    disc_number: int             # 1-based disc index
    total_discs: int             # Total discs count
    title: str                   # Track title
    artist: str                  # Artist name
    album: str                   # Album title
    date: str                    # Release year/date (e.g., "2024")
    genre: str                   # Music genre
    album_artist: str = ""       # Album representative artist (ID3 TPE2 / MP4 aART)
    encoder: str = "CD Ripping App (iTunes Compatible)"
    is_customized: bool = False  # Tracked for overwrite confirmation (CHALLENGE-003)

    @property
    def track_tag_value(self) -> str:
        """FFmpeg track tag formatted as 'X/Y' or 'X'."""
        return f"{self.track_number}/{self.total_tracks}" if self.total_tracks > 0 else str(self.track_number)

    @property
    def disc_tag_value(self) -> str:
        """FFmpeg disc tag formatted as 'X/Y' or 'X'."""
        return f"{self.disc_number}/{self.total_discs}" if self.total_discs > 0 else str(self.disc_number)

    def to_metadata_dict(self) -> Dict[str, str]:
        """Convert to FFmpeg metadata dictionary, stripping empty tags (CHALLENGE-008)."""
        raw = {
            "title": self.title.strip(),
            "artist": self.artist.strip(),
            "album_artist": self.album_artist.strip(),
            "album": self.album.strip(),
            "track": self.track_tag_value,
            "disc": self.disc_tag_value,
            "date": self.date.strip(),
            "genre": self.genre.strip(),
            "encoder": self.encoder.strip(),
        }
        return {k: v for k, v in raw.items() if v}

    @classmethod
    def create_default(
        cls,
        track_number: int,
        total_tracks: int,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        disc_number: int = 1,
        total_discs: int = 1,
        date: str = "",
        genre: str = "",
        album_artist: str = "",
        encoder: str = "CD Ripping App (iTunes Compatible)",
        is_customized: bool = False,
    ) -> "TrackTagData":
        return cls(
            track_number=track_number,
            total_tracks=max(1, total_tracks),
            disc_number=disc_number,
            total_discs=max(1, total_discs),
            title=title.strip() if (title and title.strip()) else f"Track {track_number:02d}",
            artist=artist.strip() if (artist and artist.strip()) else "Unknown Artist",
            album=album.strip() if (album and album.strip()) else "Unknown Album",
            date=date.strip(),
            genre=genre.strip(),
            album_artist=album_artist.strip(),
            encoder=encoder.strip(),
            is_customized=is_customized,
        )
