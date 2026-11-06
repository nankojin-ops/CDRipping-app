"""Audio Rip Pipeline orchestrating sector reading, rate calculation, and FFmpeg encoding."""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Callable, Dict, Optional

from cdripper.domain.exceptions import CDRipperError
from cdripper.domain.models import (
    AlbumMetadata,
    DiscTOC,
    RipConfig,
    RipProgress,
    TrackTagData,
    TrackTOC,
)
from cdripper.hardware.interface import ICDDrive
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.pipeline.ffmpeg_encoder import FFmpegEncoder, sanitize_filename

DEFAULT_BATCH_SECTORS = 25  # 1/3秒分 (58,800 bytes)


def read_track_sectors(
    drive: ICDDrive,
    track: TrackTOC,
    on_chunk: Callable[[bytes], None],
    cancel_token: Optional[threading.Event] = None,
    batch_size: int = DEFAULT_BATCH_SECTORS,
) -> None:
    """
    Read raw CD-DA audio sectors for a single track with strict boundary control.
    Uses batch = min(batch_size, remaining) to never exceed track bounds (FINDING-006, TC-RIP-03).
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size}")

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


def resolve_track_output_path(
    base_output_dir: str,
    disc_number: int,
    track_number: int,
    track_title: str,
    album_artist: Optional[str] = None,
    album_name: Optional[str] = None,
    ext: str = ".m4a",
    filename_template: str = "{disc_number}-{track_num:02d} {title}{ext}",
    max_component_length: int = 60,
) -> str:
    """
    Resolve hierarchical output path: <base_output_dir>/<safe_artist>/<safe_album>/<safe_filename>
    with strict sanitization, path traversal prevention, and safe template substitution.
    """
    # 1. 厳格な型変換 (CHALLENGE-005)
    try:
        disc_num = max(1, int(disc_number))
    except (ValueError, TypeError):
        disc_num = 1

    try:
        trk_num = max(1, int(track_number))
    except (ValueError, TypeError):
        trk_num = 1

    def _is_empty_or_placeholder(val: str) -> bool:
        if not val or val == "Unknown":
            return True
        # 禁止文字置換後アンダースコアやスペース、ドットのみしか残っていない場合も空とみなす (TC-NEG-007)
        return not bool(re.sub(r"[\s_.]", "", val))

    # 2. 空・空白・サニタイズ後の明示的フォールバック (AC-002, CHALLENGE-002)
    # FIND-SEC-012: 深層ベースディレクトリ時の動的コンポーネント長抑制 (MAX_PATH 260文字対策)
    abs_base_len = len(os.path.abspath(base_output_dir))
    remaining_len = max(30, 250 - abs_base_len)
    eff_comp_len = min(max_component_length, max(10, remaining_len // 3))

    raw_artist = (album_artist or "").strip()
    safe_artist = sanitize_filename(raw_artist, max_length=eff_comp_len)
    if _is_empty_or_placeholder(safe_artist):
        safe_artist = "Unknown Artist"

    raw_album = (album_name or "").strip()
    safe_album = sanitize_filename(raw_album, max_length=eff_comp_len)
    if _is_empty_or_placeholder(safe_album):
        safe_album = "Unknown Album"

    raw_title = (track_title or "").strip()
    safe_title = sanitize_filename(raw_title, max_length=eff_comp_len)
    if _is_empty_or_placeholder(safe_title):
        safe_title = f"Track {trk_num:02d}"

    # 3. Windows ドライブ・大文字小文字・UNC 安全なパストラバーサル防御 (CHALLENGE-001)
    abs_base = os.path.normcase(os.path.abspath(base_output_dir))
    target_dir = os.path.abspath(os.path.join(base_output_dir, safe_artist, safe_album))
    norm_target = os.path.normcase(target_dir)

    try:
        common = os.path.commonpath([abs_base, norm_target])
        if common != abs_base:
            target_dir = os.path.abspath(base_output_dir)
    except ValueError:
        # ドライブ文字不一致やUNCパス混在時の安全なフォールバック
        target_dir = os.path.abspath(base_output_dir)

    # 4. 安全なテンプレートフォーマットとサニタイズ (CHALLENGE-004, CHALLENGE-005, FIND-CR-003)
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    fmt_kwargs = {
        "disc_number": disc_num,
        "track_num": trk_num,
        "track_number": trk_num,  # FIND-CR-003: alias for user convenience
        "title": safe_title,
        "ext": safe_ext,
    }
    try:
        filename = filename_template.format(**fmt_kwargs)
    except Exception:
        filename = f"{disc_num}-{trk_num:02d} {safe_title}{safe_ext}"

    if not filename.endswith(safe_ext):
        filename = f"{filename}{safe_ext}"

    # ファイル名ベース部（拡張子除く）のNTFS禁止文字置換・最大長制限
    base_name, f_ext = os.path.splitext(filename)
    safe_base = sanitize_filename(base_name, max_length=eff_comp_len)
    filename = f"{safe_base}{f_ext}"

    full_path = os.path.join(target_dir, filename)

    # FIND-SEC-012: Windows MAX_PATH (260文字) 制限対策の多重防御ガード
    abs_len = len(os.path.abspath(full_path))
    if abs_len > 255:
        overflow = abs_len - 255
        trimmed_base_len = max(4, len(safe_base) - overflow)
        safe_base = safe_base[:trimmed_base_len]
        filename = f"{safe_base}{f_ext}"
        full_path = os.path.join(target_dir, filename)

    return full_path


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
        track_tags: Optional[Dict[int, TrackTagData]] = None,
    ) -> None:
        """
        Rip all audio tracks in TOC, apply metadata, and encode to configured format.
        When track_tags is provided, individual track metadata takes strict priority.
        """
        os.makedirs(config.output_dir, exist_ok=True)

        matched_tracks, _ = (
            ITunesApiClient.match_tracks_with_toc(toc, album, disc_number)
            if album
            else ([(t, None) for t in toc.tracks], False)
        )

        artwork_data = album.artwork_data if album else None
        total_tracks = len(toc.tracks)
        seen_output_paths: set[str] = set()

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
            custom_tag = track_tags.get(track_num) if track_tags else None

            if custom_tag is not None:
                eff_disc_num = custom_tag.disc_number
                eff_track_num = custom_tag.track_number
                eff_title = custom_tag.title
                eff_album_artist = custom_tag.album_artist or custom_tag.artist
                eff_album = custom_tag.album
                metadata_dict = custom_tag.to_metadata_dict()
            else:
                eff_disc_num = disc_number
                eff_track_num = track_num
                eff_title = itunes_meta.track_title if itunes_meta else f"Track {track_num:02d}"
                eff_album_artist = (album.album_artist or album.artist_name) if album else (itunes_meta.artist_name if itunes_meta else "")
                eff_album = album.album_name if album else ""
                artist = itunes_meta.artist_name if itunes_meta else (album.artist_name if album else "Unknown Artist")
                year = album.release_year if album else ""
                genre = album.genre if album else ""

                raw_dict = {
                    "title": eff_title,
                    "artist": artist,
                    "album": eff_album if eff_album else "Unknown Album",
                    "track": f"{track_num}/{total_tracks}",
                    "disc": f"{disc_number}/{album.total_discs if album else 1}",
                    "date": year,
                    "genre": genre,
                    "encoder": "CD Ripping App (iTunes Compatible)",
                }
                metadata_dict = {k: v.strip() for k, v in raw_dict.items() if v and v.strip()}

            output_path = resolve_track_output_path(
                base_output_dir=config.output_dir,
                disc_number=eff_disc_num,
                track_number=eff_track_num,
                track_title=eff_title,
                album_artist=eff_album_artist,
                album_name=eff_album,
                ext=config.format.extension,
                filename_template=config.filename_template,
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if output_path in seen_output_paths or os.path.exists(output_path):
                base, fext = os.path.splitext(output_path)
                collision_idx = 1
                candidate = f"{base}_{collision_idx}{fext}"
                while candidate in seen_output_paths or os.path.exists(candidate):
                    collision_idx += 1
                    candidate = f"{base}_{collision_idx}{fext}"
                output_path = candidate
            seen_output_paths.add(output_path)

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
                            status_text=f"Ripping Track {track_idx}/{total_tracks}: {eff_title}",
                            is_finished=False,
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
                raise CDRipperError(f"Failed while ripping track {track_idx}: {e}")

        # All tracks finished successfully
        progress_callback(
            RipProgress(
                current_track=total_tracks,
                total_tracks=total_tracks,
                track_progress_percent=100.0,
                overall_progress_percent=100.0,
                current_speed_x=0.0,
                status_text="Ripping completed successfully.",
                is_finished=True,
            )
        )
