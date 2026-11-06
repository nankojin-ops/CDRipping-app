"""Unit tests for FFmpeg encoder (TC-ENC-01 - TC-ENC-08, FIND-012, FIND-013, FIND-014)."""
import os
import unittest
from unittest.mock import MagicMock, patch

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

    def test_sanitize_filename_reserved_including_conin_conout(self):
        """FIND-012 (SEC-006): CONIN$ および CONOUT$ のエスケープ"""
        self.assertEqual(sanitize_filename("CONIN$"), "_CONIN$")
        self.assertEqual(sanitize_filename("CONOUT$"), "_CONOUT$")
        self.assertEqual(sanitize_filename("CON"), "_CON")

    def test_sanitize_filename_reserved_with_trailing_spaces_and_dots(self):
        """SEC-008: 末尾スペースとピリオド混在時の予約名エスケープバイパス防止"""
        self.assertEqual(sanitize_filename("CON ."), "_CON")
        self.assertEqual(sanitize_filename("PRN. ."), "_PRN")
        self.assertEqual(sanitize_filename("AUX   "), "_AUX")
        self.assertEqual(sanitize_filename("NUL."), "_NUL")

    def test_sanitize_filename_control_characters_replaced(self):
        """SEC-009: 改行および ASCII 制御文字 (0x00-0x1F, 0x7F) がアンダースコアに置換されること"""
        self.assertEqual(sanitize_filename("Track\nName\r01\t"), "Track_Name_01")
        self.assertEqual(sanitize_filename("Bad\x00Track\x1fName"), "Bad_Track_Name")
        self.assertEqual(sanitize_filename("Track\x7f"), "Track_")

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
        args_alac = build_ffmpeg_args(
            output_path="C:/music/01.m4a",
            format_type=EncodeFormat.ALAC,
            metadata={"title": "ALAC Track"},
            cover_path=None,
        )
        self.assertIn("-c:a", args_alac)
        self.assertIn("alac", args_alac)

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

    def test_encoder_session_cancel_closes_stdin(self):
        """FIND-013 (SEC-007) & TC-RIP-04: cancel_and_cleanup で stdin.close() と一時ファイル消去"""
        mock_proc = MagicMock()
        mock_proc.stderr.readline.return_value = b""
        session = EncoderSession(mock_proc, temp_cover_path="dummy_cover.jpg")

        dummy_out = "dummy_test_out.m4a"
        with open(dummy_out, "w") as f:
            f.write("partial")

        session.cancel_and_cleanup(dummy_out)
        mock_proc.terminate.assert_called_once()
        mock_proc.stdin.close.assert_called()
        self.assertFalse(os.path.exists(dummy_out))

    def test_artwork_extension_png_magic_byte(self):
        """FIND-014 (REV-007): PNGマジックバイトを判定して .png 拡張子を適用すること"""
        encoder = FFmpegEncoder()
        encoder.is_ffmpeg_available = MagicMock(return_value=True)

        png_bytes = b"\x89PNG\r\n\x1a\n" + b"dummy"
        config = RipConfig(output_dir="dummy_out", format=EncodeFormat.AAC_256K)

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            session = encoder.start_encoding_session("dummy_out/track.m4a", config, {}, png_bytes)
            self.assertTrue(session.temp_cover_path.endswith(".png"))
            session._cleanup_cover()


if __name__ == "__main__":
    unittest.main()
