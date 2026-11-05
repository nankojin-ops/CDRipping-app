"""Pipeline layer for FFmpeg encoding and audio ripping orchestration."""
from cdripper.pipeline.interface import IAudioEncoder
from cdripper.pipeline.ffmpeg_encoder import (
    EncoderSession,
    FFmpegEncoder,
    build_ffmpeg_args,
    sanitize_filename,
)
from cdripper.pipeline.rip_pipeline import AudioRipPipeline

__all__ = [
    "IAudioEncoder",
    "EncoderSession",
    "FFmpegEncoder",
    "build_ffmpeg_args",
    "sanitize_filename",
    "AudioRipPipeline",
]