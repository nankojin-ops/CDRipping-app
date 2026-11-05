"""Audio Rip Pipeline orchestrating sector reading, rate calculation, and FFmpeg encoding."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

from cdripper.domain.exceptions import CDRipperError
from cdripper.domain.models import (
    AlbumMetadata,
    DiscTOC,
    RipConfig,
    RipProgress,
    TrackTOC,
)
from cdripper.hardware.interface import ICDDrive
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.pipeline.ffmpeg_encoder import FFmpegEncoder, sanitize_filename


def read_track_sectors(
    drive: ICDDrive,
    track: TrackTOC,
    on_chunk: Callable[[bytes], None],
    cancel_token: Optional[threading.Event] = None,
    batch_size: int = 75,
) -> None:
    """
    Read raw CD-DA audio sectors for a single track with strict boundary control.
    Uses batch = min(batch_size, remaining) to never exceed track bounds (FINDING-006, TC-RIP-03).
    """
    remaining = track.sector_count
    current_lba = track.start_lba

    while remaining > 0:
        if cancel_token and cancel_token.is_set():
            break

        count = min(batch_size, remaining)
        chunk = drive.read_sectors_raw(current_lba, count)
        on_chunk(chunk)

        current_lba += count
        remaining -= count


class AudioRipPipeline:
    """Orchestrates ripping an entire disc to destination files."""

    def __init__(self, encoder: Optional[FFmpegEncoder] = None):
        self.encoder = encoder or FFmpegEncoder()

    def rip_disc(
        self,
        drive: ICDDrive,
        toc: DiscTOC,
        album: Optional[AlbumMetadata],
        config: RipConfig,
        progress_callback: Callable[[RipProgress], None],
        cancel_event: threading.Event,
        disc_number: int = 1,
    ) -> None:
        """
        Rip all audio tracks in TOC, apply metadata, and encode to configured format.
        """
        os.makedirs(config.output_dir, exist_ok=True)

        matched_tracks, _ = (
            ITunesApiClient.match_tracks_with_toc(toc, album, disc_number)
            if album
            else ([(t, None) for t in toc.tracks], False)
        )

        artwork_data = album.artwork_data if album else None
        total_tracks = len(toc.tracks)

        drive.set_read_speed(config.selected_speed_x)

        for track_idx, (track_toc, itunes_meta) in enumerate(matched_tracks, start=1):
            if cancel_event.is_set():
                progress_callback(
                    RipProgress(
                        current_track=track_idx,
                        total_tracks=total_tracks,
                        track_progress_percent=0.0,
                        overall_progress_percent=float((track_idx - 1) / total_tracks * 100),
                        current_speed_x=0.0,
                        status_text="Cancelled by user.",
                        is_finished=True,
                    )
                )
                return

            if not track_toc.is_audio:
                continue

            track_num = track_toc.track_number
            title = itunes_meta.track_title if itunes_meta else f"Track {track_num:02d}"
            artist = itunes_meta.artist_name if itunes_meta else (album.artist_name if album else "Unknown Artist")
            album_name = album.album_name if album else "Unknown Album"
            year = album.release_year if album else ""
            genre = album.genre if album else ""

            safe_title = sanitize_filename(title)
            ext = config.format.extension
            filename = config.filename_template.format(
                track_num=track_num,
                title=safe_title,
                ext=ext,
            )
            if not filename.endswith(ext):
                filename = f"{filename}{ext}"

            output_path = os.path.join(config.output_dir, filename)

            metadata_dict = {
                "title": title,
                "artist": artist,
                "album": album_name,
                "track": f"{track_num}/{total_tracks}",
                "disc": f"{disc_number}/{album.total_discs if album else 1}",
                "date": year,
                "genre": genre,
                "encoder": "CD Ripping App (iTunes Compatible)",
            }

            session = self.encoder.start_encoding_session(
                output_path=output_path,
                config=config,
                track_metadata=metadata_dict,
                artwork_bytes=artwork_data,
            )

            start_time = time.time()
            sectors_read = 0
            track_sectors = track_toc.sector_count

            try:
                def on_chunk(chunk: bytes) -> None:
                    nonlocal sectors_read
                    session.write_pcm(chunk)
                    sectors_read += len(chunk) // 2352

                    elapsed = max(0.001, time.time() - start_time)
                    cur_speed = (sectors_read / 75.0) / elapsed

                    track_pct = min(100.0, (sectors_read / max(1, track_sectors)) * 100.0)
                    overall_pct = (
                        (track_idx - 1) / total_tracks * 100.0
                        + track_pct / total_tracks
                    )

                    progress_callback(
                        RipProgress(
                            current_track=track_idx,
                            total_tracks=total_tracks,
                            track_progress_percent=track_pct,
                            overall_progress_percent=overall_pct,
                            current_speed_x=cur_speed,
                            status_text=f"Ripping Track {track_idx}/{total_tracks}: {title}",
                        )
                    )

                read_track_sectors(
                    drive=drive,
                    track=track_toc,
                    on_chunk=on_chunk,
                    cancel_token=cancel_event,
                )

                if cancel_event.is_set():
                    session.cancel_and_cleanup(output_path)
                    progress_callback(
                        RipProgress(
                            current_track=track_idx,
                            total_tracks=total_tracks,
                            track_progress_percent=0.0,
                            overall_progress_percent=float((track_idx - 1) / total_tracks * 100),
                            current_speed_x=0.0,
                            status_text="Cancelled by user.",
                            is_finished=True,
                        )
                    )
                    return

                session.finish()

            except Exception as e:
                session.cancel_and_cleanup(output_path)
                progress_callback(
                    RipProgress(
                        current_track=track_idx,
                        total_tracks=total_tracks,
                        track_progress_percent=0.0,
                        overall_progress_percent=float((track_idx - 1) / total_tracks * 100),
                        current_speed_x=0.0,
                        status_text=f"Error on track {track_idx}: {e}",
                        is_finished=True,
                        error_message=str(e),
                    )
                )
                raise CDRipperError(f"Ripping failed on track {track_idx}: {e}")

        progress_callback(
            RipProgress(
                current_track=total_tracks,
                total_tracks=total_tracks,
                track_progress_percent=100.0,
                overall_progress_percent=100.0,
                current_speed_x=0.0,
                status_text="Ripping completed successfully!",
                is_finished=True,
            )
        )