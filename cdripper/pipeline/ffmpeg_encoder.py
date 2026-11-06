"""FFmpeg audio encoder with pipe deadlock prevention and NTFS filename sanitization."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Dict, List, Optional

from cdripper.domain.exceptions import EncodingError, FFmpegNotFoundError
from cdripper.domain.models import EncodeFormat, RipConfig


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """
    Sanitize filename for Windows NTFS file systems.
    - Replaces invalid characters: ASCII control chars, \\ / : * ? " < > | with '_' (SEC-009)
    - Strips trailing dots and spaces first to prevent bypass (SEC-008)
    - Handles reserved device names including CONIN$ and CONOUT$ (FIND-012, SEC-006)
    - Limits string length to prevent MAX_PATH overflow
    """
    if not name:
        return "Unknown"

    # Strip leading/trailing whitespace first
    sanitized = name.strip()

    # Replace NTFS invalid characters including control characters (0x00-0x1f, 0x7f) (SEC-009)
    sanitized = re.sub(r'[\x00-\x1f\x7f\\/*?:"<>|]', "_", sanitized)

    # Strip trailing dots and spaces BEFORE matching reserved device names (SEC-008)
    sanitized = re.sub(r"[.\s]+$", "", sanitized).strip()

    # FIND-012 (SEC-006): Add CONIN$ and CONOUT$ to reserved pattern
    reserved_pattern = r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]|CONIN\$|CONOUT\$)(\..*)?$"
    if re.match(reserved_pattern, sanitized, re.IGNORECASE):
        sanitized = f"_{sanitized}"

    # Re-strip trailing dots/spaces in case reserved prefix modification introduced any
    sanitized = re.sub(r"[.\s]+$", "", sanitized)

    if not sanitized:
        sanitized = "Unknown"

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip(" .")

    return sanitized


def build_ffmpeg_args(
    output_path: str,
    format_type: EncodeFormat,
    metadata: Dict[str, str],
    cover_path: Optional[str] = None,
    ffmpeg_bin: str = "ffmpeg",
) -> List[str]:
    """
    Build dynamic FFmpeg command line arguments array.
    Guarantees shell=False safe execution and proper stream mapping.
    """
    args = [
        ffmpeg_bin,
        "-y",
        "-f", "s16le",
        "-ar", "44100",
        "-ac", "2",
        "-i", "pipe:0",
    ]

    has_cover = bool(cover_path and os.path.exists(cover_path))

    if has_cover:
        args.extend(["-i", cover_path])
        args.extend([
            "-map", "0:a",
            "-map", "1:0",
            "-c:v", "copy",
            "-disposition:v:0", "attached_pic",
        ])
    else:
        args.extend(["-map", "0:a"])

    if format_type == EncodeFormat.AAC_256K:
        args.extend(["-c:a", "aac", "-b:a", "256k"])
    elif format_type == EncodeFormat.ALAC:
        args.extend(["-c:a", "alac"])
    elif format_type == EncodeFormat.MP3_320K:
        args.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3"])

    for key, val in metadata.items():
        if val is not None and str(val).strip():
            args.extend(["-metadata", f"{key}={val}"])

    args.append(output_path)
    return args


class EncoderSession:
    """
    Encapsulates an active FFmpeg encoding subprocess with background stderr drain.
    Prevents pipe deadlock and handles cancellation cleanup.
    """

    def __init__(self, process: subprocess.Popen, temp_cover_path: Optional[str]):
        self.process = process
        self.temp_cover_path = temp_cover_path
        self.stderr_lines: List[str] = []
        self._is_closed = False

        self._reader_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._reader_thread.start()

    def _drain_stderr(self) -> None:
        try:
            if self.process.stderr:
                for line in iter(self.process.stderr.readline, b""):
                    decoded = line.decode("utf-8", errors="replace")
                    self.stderr_lines.append(decoded)
        except Exception:
            pass

    def write_pcm(self, data: bytes) -> None:
        """Write raw PCM chunk into FFmpeg stdin."""
        if self._is_closed:
            raise EncodingError("Encoder session is already closed.")
        try:
            if self.process.stdin:
                self.process.stdin.write(data)
                self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise EncodingError(f"FFmpeg stdin pipe broken: {e}")

    def finish(self) -> None:
        """Close stdin, wait for encoding to complete, and cleanup cover image."""
        if self._is_closed:
            return
        self._is_closed = True

        try:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.wait(timeout=30)
        except Exception as e:
            self.process.kill()
            raise EncodingError(f"FFmpeg process did not terminate cleanly: {e}")
        finally:
            self._cleanup_cover()

        if self.process.returncode != 0:
            tail_errors = "".join(self.stderr_lines[-20:])
            raise EncodingError(
                f"FFmpeg failed with return code {self.process.returncode}:\n{tail_errors}"
            )

    def cancel_and_cleanup(self, output_path: str) -> None:
        """Terminate process and purge incomplete output and temp cover files (FIND-013)."""
        self._is_closed = True
        try:
            self.process.terminate()
            self.process.wait(timeout=3)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        finally:
            # FIND-013 (SEC-007): Ensure stdin is closed on cancellation
            if self.process.stdin:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass

            self._cleanup_cover()
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass

    def _cleanup_cover(self) -> None:
        if self.temp_cover_path and os.path.exists(self.temp_cover_path):
            try:
                os.remove(self.temp_cover_path)
            except OSError:
                pass
        self.temp_cover_path = None


class FFmpegEncoder:
    """FFmpeg encoder management and session creation."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def is_ffmpeg_available(self) -> bool:
        """Verify FFmpeg binary can be invoked."""
        try:
            res = subprocess.run(
                [self.ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def start_encoding_session(
        self,
        output_path: str,
        config: RipConfig,
        track_metadata: Dict[str, str],
        artwork_bytes: Optional[bytes] = None,
    ) -> EncoderSession:
        """Start a streaming encoding session."""
        if not self.is_ffmpeg_available():
            raise FFmpegNotFoundError(
                f"FFmpeg executable not found at '{self.ffmpeg_path}'. Please install FFmpeg."
            )

        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        temp_cover_path = None
        if artwork_bytes:
            # FIND-014 (REV-007): Detect PNG magic bytes or default to JPEG
            ext = ".png" if artwork_bytes.startswith(b"\x89PNG") else ".jpg"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                tf.write(artwork_bytes)
                temp_cover_path = tf.name

        args = build_ffmpeg_args(
            output_path=output_path,
            format_type=config.format,
            metadata=track_metadata,
            cover_path=temp_cover_path,
            ffmpeg_bin=self.ffmpeg_path,
        )

        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                shell=False,
            )
            return EncoderSession(proc, temp_cover_path)
        except Exception as e:
            if temp_cover_path and os.path.exists(temp_cover_path):
                os.remove(temp_cover_path)
            raise EncodingError(f"Failed to start FFmpeg subprocess: {e}")
