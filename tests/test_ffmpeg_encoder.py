"""Unit tests for FFmpeg encoder, argument construction, and filename sanitization (TC-ENC-01 - TC-ENC-08)."""
import os
import unittest
from unittest.mock import MagicMock

from cdripper.domain.exceptions import FFmpegNotFoundError
from cdripper.domain.models import EncodeFormat, RipConfig
from cdripper.pipeline.ffmpeg_encoder import (
    EncoderSession,
    FFmpegEncoder,
    build_ffmpeg_args,
    sanitize_filename,
)


class TestFFmpegEncoder(unittest.TestCase):
    def test_sanitize_filename_ntfs_prohibited(self):
        """TC-ENC-04: NTFS禁止文字置換"""
        bad_name = 'AC/DC: Who Made Who? "Live" <2026> | test*name'
        cleaned = sanitize_filename(bad_name)
        for char in r'\/*?:"<>|':
            self.assertNotIn(char, cleaned)

    def test_sanitize_filename_windows_reserved(self):
        """TC-ENC-05: Windows予約デバイス名の回避"""
        self.assertEqual(sanitize_filename("CON"), "_CON")
        self.assertEqual(sanitize_filename("PRN"), "_PRN")
        self.assertEqual(sanitize_filename("AUX.mp3"), "_AUX.mp3")
        self.assertEqual(sanitize_filename("NUL"), "_NUL")
        self.assertEqual(sanitize_filename("COM1"), "_COM1")

    def test_sanitize_filename_trailing_periods(self):
        """末尾ピリオド・空白のトリム"""
        cleaned = sanitize_filename("Track Title...")
        self.assertEqual(cleaned, "Track Title")

    def test_sanitize_filename_max_length_truncation(self):
        """TC-ENC-06: 120文字を超える長いファイル名の安全な切り詰め"""
        long_name = "A" * 150
        cleaned = sanitize_filename(long_name, max_length=120)
        self.assertLessEqual(len(cleaned), 120)
        self.assertEqual(cleaned, "A" * 120)

    def test_sanitize_filename_unicode_and_emojis(self):
        """TC-ENC-07: 日本語全角文字、絵文字、ウムラウトが破壊されず維持されること"""
        jp_name = "01 - 宇多田ヒカル - 初恋"
        self.assertEqual(sanitize_filename(jp_name), jp_name)

        emoji_name = "Track 🎵 Beats"
        self.assertEqual(sanitize_filename(emoji_name), emoji_name)

        umlaut_name = "Mötley Crüe - Kickstart My Heart"
        self.assertEqual(sanitize_filename(umlaut_name), umlaut_name)

    def test_build_ffmpeg_args_without_cover(self):
        """TC-ENC-01: アートワークなしAAC引数"""
        args = build_ffmpeg_args(
            output_path="C:/music/01.m4a",
            format_type=EncodeFormat.AAC_256K,
            metadata={"title": "Test Title", "artist": "Test Artist"},
            cover_path=None,
        )
        self.assertIn("-c:a", args)
        self.assertIn("aac", args)
        self.assertIn("-b:a", args)
        self.assertIn("256k", args)
        self.assertIn("-metadata", args)
        self.assertIn("title=Test Title", args)
        self.assertNotIn("-disposition:v:0", args)

    def test_build_ffmpeg_args_alac_and_mp3(self):
        """TC-ENC-03: ALAC および MP3 エンコード引数の構築"""
        # ALAC
        args_alac = build_ffmpeg_args(
            output_path="C:/music/01.m4a",
            format_type=EncodeFormat.ALAC,
            metadata={"title": "ALAC Track"},
            cover_path=None,
        )
        self.assertIn("-c:a", args_alac)
        self.assertIn("alac", args_alac)

        # MP3 320k
        args_mp3 = build_ffmpeg_args(
            output_path="C:/music/01.mp3",
            format_type=EncodeFormat.MP3_320K,
            metadata={"title": "MP3 Track"},
            cover_path=None,
        )
        self.assertIn("-c:a", args_mp3)
        self.assertIn("libmp3lame", args_mp3)
        self.assertIn("-b:a", args_mp3)
        self.assertIn("320k", args_mp3)
        self.assertIn("-id3v2_version", args_mp3)
        self.assertIn("3", args_mp3)

    def test_ffmpeg_not_found_raises_error(self):
        """TC-ENC-08: FFmpeg未インストール時の明確なエラーハンドリング"""
        encoder = FFmpegEncoder(ffmpeg_path="C:/non_existent_path_to_ffmpeg/ffmpeg.exe")
        self.assertFalse(encoder.is_ffmpeg_available())

        config = RipConfig(output_dir="C:/dummy", format=EncodeFormat.AAC_256K)
        with self.assertRaises(FFmpegNotFoundError):
            encoder.start_encoding_session("C:/dummy/out.m4a", config, {"title": "Test"})

    def test_encoder_session_cancel_and_cleanup(self):
        """TC-RIP-04: キャンセル時の一時ファイル消去"""
        mock_proc = MagicMock()
        mock_proc.stderr.readline.return_value = b""
        session = EncoderSession(mock_proc, temp_cover_path="dummy_cover.jpg")

        dummy_out = "dummy_test_out.m4a"
        with open(dummy_out, "w") as f:
            f.write("partial")

        session.cancel_and_cleanup(dummy_out)
        mock_proc.terminate.assert_called_once()
        self.assertFalse(os.path.exists(dummy_out))


if __name__ == "__main__":
    unittest.main()
