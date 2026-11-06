"""Presenter layer managing UI events, threading, and pipeline interactions."""
from __future__ import annotations

from dataclasses import replace
import queue
import threading
from typing import Dict, List, Optional

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDRipperError,
)
from cdripper.domain.models import (
    AlbumMetadata,
    AlbumTagData,
    DiscTOC,
    DriveInfo,
    EncodeFormat,
    RipConfig,
    RipProgress,
    TrackTagData,
)
from cdripper.domain.validation import sanitize_tag_string
from cdripper.hardware.interface import ICDDrive
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer
from cdripper.hardware.spti_drive import WindowsSPTICDDrive
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.metadata.interface import IMetadataProvider
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.pipeline.ffmpeg_encoder import FFmpegEncoder
from cdripper.pipeline.rip_pipeline import AudioRipPipeline
from cdripper.ui.artwork_helper import normalize_artwork


class PresenterEvent:
    """Event messages dispatched from worker threads to UI thread."""

    DRIVES_LOADED = "DRIVES_LOADED"
    TOC_LOADED = "TOC_LOADED"
    METADATA_LOADED = "METADATA_LOADED"
    SEARCH_RESULTS = "SEARCH_RESULTS"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    ERROR = "ERROR"
    LOG = "LOG"
    TRACK_TAG_UPDATED = "TRACK_TAG_UPDATED"  # AC-002, CHALLENGE-006
    ALBUM_TAGS_UPDATED = "ALBUM_TAGS_UPDATED"  # AC-003, FIND-006


class CDRipperPresenter:
    """Presenter managing application business logic and threading."""

    def __init__(
        self,
        drive: Optional[ICDDrive] = None,
        metadata_provider: Optional[IMetadataProvider] = None,
        encoder: Optional[FFmpegEncoder] = None,
    ):
        self.drive: ICDDrive = drive or WindowsSPTICDDrive()
        self.metadata_provider: IMetadataProvider = metadata_provider or ITunesApiClient()
        self.encoder: FFmpegEncoder = encoder or FFmpegEncoder()
        self.pipeline: AudioRipPipeline = AudioRipPipeline(self.encoder)

        self.event_queue: queue.Queue = queue.Queue()
        self.cancel_event: threading.Event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

        self.current_drives: List[DriveInfo] = []
        self.selected_drive: Optional[DriveInfo] = None
        self.current_toc: Optional[DiscTOC] = None
        self.current_album: Optional[AlbumMetadata] = None
        self.selected_disc: int = 1
        self.is_virtual_mode: bool = isinstance(self.drive, VirtualCDDrive)

        # SSOT for track metadata tags (CHALLENGE-006, CHALLENGE-002)
        self.track_tags: Dict[int, TrackTagData] = {}
        self.is_ripping: bool = False

    def switch_to_virtual_drive(self, has_media: bool = True) -> None:
        """Switch current drive to VirtualCDDrive (for testing or fallback)."""
        if self.is_ripping:
            self.event_queue.put((PresenterEvent.ERROR, "Cannot switch drive while ripping is in progress."))
            return
        self.drive.close()
        self.drive = VirtualCDDrive(has_media=has_media)
        self.is_virtual_mode = True
        self.log("Switched to Virtual CD Drive mode.")
        self.scan_drives()

    def log(self, message: str) -> None:
        """Push a log message to the event queue."""
        self.event_queue.put((PresenterEvent.LOG, message))

    def scan_drives(self) -> None:
        """Scan connected drives asynchronously."""
        if self.is_ripping:
            self.event_queue.put((PresenterEvent.ERROR, "Cannot scan drives while ripping is in progress."))
            return

        def run():
            try:
                self.log("Scanning optical drives...")
                drives = self.drive.list_drives()
                self.current_drives = drives
                self.event_queue.put((PresenterEvent.DRIVES_LOADED, drives))
                self.log(f"Found {len(drives)} drive(s).")
            except Exception as e:
                self.log(f"Drive scan error: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Failed to list drives: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def select_drive(self, drive_letter: str) -> None:
        """Open specified drive and read its TOC asynchronously."""
        if self.is_ripping:
            self.event_queue.put((PresenterEvent.ERROR, "Cannot change drive while ripping is in progress."))
            return

        def run():
            try:
                self.log(f"Opening drive {drive_letter}...")
                self.drive.open(drive_letter)
                for d in self.current_drives:
                    if d.drive_letter == drive_letter:
                        self.selected_drive = d
                        break

                self.log(f"Reading TOC from drive {drive_letter}...")
                toc = self.drive.read_toc()
                self.current_toc = toc

                # Initialize default SSOT track tags (AC-001)
                self.track_tags.clear()
                total_tracks = toc.total_tracks
                for t in toc.tracks:
                    if t.is_audio:
                        self.track_tags[t.track_number] = TrackTagData.create_default(
                            track_number=t.track_number,
                            total_tracks=total_tracks,
                            disc_number=self.selected_disc,
                            total_discs=1,
                            encoder="CD Ripping App (iTunes Compatible)",
                        )

                self.event_queue.put((PresenterEvent.TOC_LOADED, toc))
                self.log(f"TOC loaded successfully: {toc.total_tracks} tracks, {toc.total_duration_seconds:.1f}s.")
            except CDDriveNoMediaError:
                self.log(f"No disc inserted in drive {drive_letter}.")
                self.event_queue.put((PresenterEvent.ERROR, "No CD media inserted in drive."))
            except CDDriveAccessDeniedError:
                self.log(f"Access denied to drive {drive_letter}. Need Administrator privileges.")
                self.event_queue.put((
                    PresenterEvent.ERROR,
                    "Access denied to CD drive. Please run as Administrator or switch to Virtual CD Mode."
                ))
            except Exception as e:
                self.log(f"Failed to load TOC: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Error reading disc: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def search_album_metadata(self, query: str) -> None:
        """Search albums on iTunes."""
        def run():
            try:
                self.log(f"Searching iTunes for '{query}'...")
                albums = self.metadata_provider.search_albums(query)
                self.event_queue.put((PresenterEvent.SEARCH_RESULTS, albums))
                self.log(f"Found {len(albums)} album(s) matching '{query}'.")
            except Exception as e:
                self.log(f"Search failed: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"iTunes Search failed: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def apply_album_metadata(self, collection_id: int, overwrite_customized: bool = True) -> None:
        """Lookup album tracks and apply artwork, updating SSOT track tags (CHALLENGE-003, CHALLENGE-006)."""
        def run():
            try:
                self.log(f"Retrieving album tracks for collection ID {collection_id}...")
                album = self.metadata_provider.lookup_album_tracks(collection_id)

                if album.artwork_url:
                    self.log("Downloading high-resolution cover artwork...")
                    raw_art = self.metadata_provider.download_artwork(album.artwork_url)
                    album.artwork_data = normalize_artwork(raw_art) if raw_art else None

                album.album_artist = album.artist_name
                self.current_album = album

                # Sync album metadata to track_tags SSOT
                if self.current_toc:
                    matched_tracks, _ = ITunesApiClient.match_tracks_with_toc(
                        self.current_toc, album, self.selected_disc
                    )
                    for toc_track, itunes_track in matched_tracks:
                        if not toc_track:
                            continue
                        trk_num = toc_track.track_number
                        existing = self.track_tags.get(trk_num)
                        if existing and existing.is_customized and not overwrite_customized:
                            continue  # Protect customized track (TC-SSOT-003)

                        clean_year = album.release_year if (album.release_year and album.release_year.isdigit() and len(album.release_year) == 4) else ""
                        self.track_tags[trk_num] = TrackTagData(
                            track_number=trk_num,
                            total_tracks=self.current_toc.total_tracks,
                            disc_number=self.selected_disc,
                            total_discs=album.total_discs,
                            title=itunes_track.track_title if itunes_track else f"Track {trk_num:02d}",
                            artist=itunes_track.artist_name if itunes_track else album.artist_name,
                            album=album.album_name,
                            date=clean_year,
                            genre=album.genre,
                            album_artist=album.artist_name,
                            encoder="CD Ripping App (iTunes Compatible)",
                            is_customized=False if overwrite_customized else (existing.is_customized if existing else False),
                        )
                        self.event_queue.put((PresenterEvent.TRACK_TAG_UPDATED, (trk_num, self.track_tags[trk_num])))

                self.event_queue.put((PresenterEvent.METADATA_LOADED, album))
                self.log(f"Applied metadata: '{album.album_name}' by '{album.artist_name}' ({len(album.tracks)} tracks).")
            except Exception as e:
                self.log(f"Failed to apply album metadata: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Failed to retrieve album details: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def get_track_tag(self, track_number: int) -> Optional[TrackTagData]:
        """Retrieve tag data for a specific track."""
        return self.track_tags.get(track_number)

    def get_all_track_tags(self) -> Dict[int, TrackTagData]:
        """Return shallow copy of all track tags dictionary."""
        return dict(self.track_tags)

    def has_customized_tracks(self) -> bool:
        """Return True if any track has been manually edited by user (CHALLENGE-003)."""
        return any(t.is_customized for t in self.track_tags.values())

    def update_track_tag(self, track_number: int, tag_data: TrackTagData) -> None:
        """Update single track tag SSOT and notify UI (AC-002)."""
        self.track_tags[track_number] = tag_data
        self.event_queue.put((PresenterEvent.TRACK_TAG_UPDATED, (track_number, tag_data)))
        self.log(f"Updated tags for track {track_number}: '{tag_data.title}' (customized={tag_data.is_customized})")

    def update_album_tags(self, album_data: AlbumTagData) -> None:
        """
        Batch update album-level tags across all tracks, synchronize current_album and selected_disc.
        Protects track-specific titles, track numbers, and customized artists.
        (AC-003, FIND-003, FIND-004, FIND-006)
        """
        if self.is_ripping:
            self.event_queue.put((PresenterEvent.ERROR, "Cannot edit album tags while ripping is in progress."))
            return

        # FIND-004: Synchronize selected_disc
        self.selected_disc = album_data.disc_number

        clean_year = (
            album_data.date
            if (album_data.date and album_data.date.isdigit() and len(album_data.date) == 4)
            else ""
        )

        # Update or synthesize current_album
        if self.current_album:
            self.current_album.album_name = album_data.album
            if album_data.album_artist:
                self.current_album.artist_name = album_data.album_artist
            self.current_album.album_artist = album_data.album_artist
            self.current_album.release_year = clean_year
            self.current_album.genre = album_data.genre
            self.current_album.total_discs = album_data.total_discs
            self.current_album.artwork_data = album_data.artwork_data
        else:
            self.current_album = AlbumMetadata(
                collection_id=0,
                album_name=album_data.album,
                artist_name=album_data.album_artist or "Unknown Artist",
                album_artist=album_data.album_artist,
                release_year=clean_year,
                genre=album_data.genre,
                total_tracks=len(self.track_tags) if self.track_tags else 0,
                total_discs=album_data.total_discs,
                artwork_data=album_data.artwork_data,
            )

        # Update track tags SSOT for all tracks
        for trk_num, tag in list(self.track_tags.items()):
            # Artist protection rule:
            # If track has a specific artist set (and not empty or generic "Unknown Artist"),
            # keep track-specific artist unless it was matching the default.
            new_artist = tag.artist
            if (not tag.artist or tag.artist == "Unknown Artist") and album_data.album_artist:
                new_artist = album_data.album_artist

            # FIND-003: Preserve is_customized flag, do NOT blanket overwrite to True
            updated_tag = TrackTagData(
                track_number=tag.track_number,
                total_tracks=tag.total_tracks,
                disc_number=album_data.disc_number,
                total_discs=album_data.total_discs,
                title=tag.title,                      # Protected track title
                artist=new_artist,                    # Protected individual artist
                album=album_data.album,               # Propagated album title
                date=album_data.date,                 # Propagated date
                genre=album_data.genre,               # Propagated genre
                album_artist=album_data.album_artist, # Propagated album artist
                encoder=tag.encoder,
                is_customized=tag.is_customized,      # FIND-003 preserved
            )
            self.track_tags[trk_num] = updated_tag
            self.event_queue.put((PresenterEvent.TRACK_TAG_UPDATED, (trk_num, updated_tag)))

        # Notify UI of album-wide update (FIND-006)
        self.event_queue.put((PresenterEvent.ALBUM_TAGS_UPDATED, album_data))
        self.log(
            f"Updated album tags: '{album_data.album}' by '{album_data.album_artist}' "
            f"(Disc {album_data.disc_number}/{album_data.total_discs})."
        )

    def sync_album_artist_to_uncustomized(self, album: str, artist: str) -> None:
        """
        Propagate main UI album/artist changes to uncustomized tracks with sanitization (CHALLENGE-006, SEC-010).
        """
        clean_album = sanitize_tag_string(album, max_length=256)
        clean_artist = sanitize_tag_string(artist, max_length=256)
        for trk_num, tag in list(self.track_tags.items()):
            if not tag.is_customized:
                new_tag = replace(
                    tag,
                    album=clean_album if clean_album else tag.album,
                    artist=clean_artist if clean_artist else tag.artist,
                )
                self.track_tags[trk_num] = new_tag
                self.event_queue.put((PresenterEvent.TRACK_TAG_UPDATED, (trk_num, new_tag)))

    def start_ripping(self, config: RipConfig) -> None:
        """Start disc ripping pipeline with concurrency guard (CHALLENGE-002, CHALLENGE-007)."""
        if self.is_ripping:
            self.event_queue.put((PresenterEvent.ERROR, "Ripping session is already in progress."))
            return

        if not self.current_toc:
            self.event_queue.put((PresenterEvent.ERROR, "No disc TOC loaded."))
            return

        self.is_ripping = True
        self.cancel_event.clear()

        # Mathematical thread-safety: copy immutable models dict
        tags_snapshot = dict(self.track_tags)

        def progress_cb(prog: RipProgress) -> None:
            if prog.is_finished:
                self.is_ripping = False
            self.event_queue.put((PresenterEvent.PROGRESS_UPDATE, prog))

        def run():
            try:
                self.log(f"Starting ripping session to '{config.output_dir}'...")
                self.pipeline.rip_disc(
                    drive=self.drive,
                    toc=self.current_toc,
                    album=self.current_album,
                    config=config,
                    progress_callback=progress_cb,
                    cancel_event=self.cancel_event,
                    disc_number=self.selected_disc,
                    track_tags=tags_snapshot,
                )
            except Exception as e:
                self.is_ripping = False
                self.log(f"Ripping session error: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Ripping failed: {e}"))
            finally:
                self.is_ripping = False

        self.worker_thread = threading.Thread(target=run, daemon=True)
        self.worker_thread.start()

    def cancel_ripping(self) -> None:
        """Signal cancellation to ripping worker thread."""
        self.log("Cancelling rip operation...")
        self.cancel_event.set()
