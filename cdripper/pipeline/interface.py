"""Abstract base class interface for audio encoders."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

from cdripper.domain.models import RipConfig
from cdripper.pipeline.ffmpeg_encoder import EncoderSession


class IAudioEncoder(ABC):
    """Interface for encoding PCM audio streams into compressed formats with metadata."""

    @abstractmethod
    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg binary is available on the system."""
        raise NotImplementedError

    @abstractmethod
    def start_encoding_session(
        self,
        output_path: str,
        config: RipConfig,
        track_metadata: Dict[str, str],
        artwork_bytes: Optional[bytes] = None,
    ) -> EncoderSession:
        """Start a streaming encoding session accepting PCM bytes to stdin."""
        raise NotImplementedError