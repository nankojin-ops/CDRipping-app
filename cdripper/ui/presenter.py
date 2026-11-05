"""Presenter layer managing UI events, threading, and pipeline interactions."""
from __future__ import annotations

import queue
import threading
from typing import List, Optional

from cdripper.domain.exceptions import (
    CDDriveAccessDeniedError,
    CDDriveNoMediaError,
    CDRipperError,
)
from cdripper.domain.models import (
    AlbumMetadata,
    DiscTOC,
    DriveInfo,
    EncodeFormat,
    RipConfig,
    RipProgress,
)
from cdripper.hardware.interface import ICDDrive
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer
from cdripper.hardware.spti_drive import WindowsSPTICDDrive
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.metadata.interface import IMetadataProvider
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.pipeline.ffmpeg_encoder import FFmpegEncoder
from cdripper.pipeline.rip_pipeline import AudioRipPipeline


class PresenterEvent:
    """Event messages dispatched from worker threads to UI thread."""

    DRIVES_LOADED = "DRIVES_LOADED"
    TOC_LOADED = "TOC_LOADED"
    METADATA_LOADED = "METADATA_LOADED"
    SEARCH_RESULTS = "SEARCH_RESULTS"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    ERROR = "ERROR"
    LOG = "LOG"


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

    def switch_to_virtual_drive(self, has_media: bool = True) -> None:
        """Switch current drive to VirtualCDDrive (for testing or fallback)."""
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
        def run():
            try:
                self.log("Scanning optical drives...")
                drives = self.drive.list_drives()
                self.current_drives = drives
                self.event_queue.put((PresenterEvent.DRIVES_LOADED, drives))
                self.log(f"Found {len(drives)} optical drive(s).")
            except Exception as e:
                self.event_queue.put((PresenterEvent.ERROR, f"Drive scan failed: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def select_drive(self, drive_letter: str) -> None:
        """Select a drive and read its TOC asynchronously."""
        matched = [d for d in self.current_drives if d.drive_letter == drive_letter]
        if matched:
            self.selected_drive = matched[0]

        def run():
            try:
                self.log(f"Opening drive {drive_letter}...")
                self.drive.open(drive_letter)
                self.log("Reading CD Table of Contents...")
                toc = self.drive.read_toc()
                self.current_toc = toc
                self.event_queue.put((PresenterEvent.TOC_LOADED, toc))
                self.log(f"TOC loaded: {toc.total_tracks} tracks, duration {toc.total_duration_seconds:.1f}s.")
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

    def apply_album_metadata(self, collection_id: int) -> None:
        """Lookup album tracks and apply artwork."""
        def run():
            try:
                self.log(f"Retrieving album tracks for collection ID {collection_id}...")
                album = self.metadata_provider.lookup_album_tracks(collection_id)

                if album.artwork_url:
                    self.log("Downloading high-resolution cover artwork...")
                    album.artwork_data = self.metadata_provider.download_artwork(album.artwork_url)

                self.current_album = album
                self.event_queue.put((PresenterEvent.METADATA_LOADED, album))
                self.log(f"Applied metadata: '{album.album_name}' by '{album.artist_name}' ({len(album.tracks)} tracks).")
            except Exception as e:
                self.log(f"Failed to apply album metadata: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Failed to retrieve album details: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def start_ripping(self, config: RipConfig) -> None:
        """Start disc ripping pipeline in background worker thread."""
        if not self.current_toc:
            self.event_queue.put((PresenterEvent.ERROR, "No disc TOC loaded."))
            return

        self.cancel_event.clear()

        def progress_cb(prog: RipProgress) -> None:
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
                )
            except Exception as e:
                self.log(f"Ripping session error: {e}")
                self.event_queue.put((PresenterEvent.ERROR, f"Ripping failed: {e}"))

        self.worker_thread = threading.Thread(target=run, daemon=True)
        self.worker_thread.start()

    def cancel_ripping(self) -> None:
        """Signal cancellation to ripping worker thread."""
        self.log("Cancelling rip operation...")
        self.cancel_event.set()