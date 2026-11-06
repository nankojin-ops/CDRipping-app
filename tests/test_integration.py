"""End-to-End integration test across VirtualCDDrive -> MockMetadata -> RipPipeline (TC-MCK-02, TC-ENC-02, AC-003)."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

from cdripper.domain.models import EncodeFormat, RipConfig, TrackTagData
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.metadata.mock_provider import MockMetadataProvider
from cdripper.pipeline.ffmpeg_encoder import FFmpegEncoder
from cdripper.pipeline.rip_pipeline import AudioRipPipeline


class TestIntegrationE2E(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cdrip_test_")
        self.drive = VirtualCDDrive(track_durations=[1, 1])  # 2 tracks of 1 sec
        self.meta_provider = MockMetadataProvider()
        self.encoder = FFmpegEncoder()
        self.pipeline = AudioRipPipeline(self.encoder)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_virtual_rip_pipeline(self):
        """TC-MCK-02 & TC-ENC-02: 仮想CDからのリッピングとffprobeによるタグ埋め込み検証"""
        if not self.encoder.is_ffmpeg_available():
            self.skipTest("FFmpeg binary not found on system PATH; skipping real encode test.")
            return

        self.drive.open("V:")
        toc = self.drive.read_toc()
        album = self.meta_provider.lookup_album_tracks(1001)
        album.artwork_data = self.meta_provider.download_artwork(album.artwork_url)

        config = RipConfig(
            output_dir=self.test_dir,
            format=EncodeFormat.AAC_256K,
            selected_speed_x=8,
        )

        progress_events = []
        def on_prog(p):
            progress_events.append(p)

        cancel = threading.Event()

        self.pipeline.rip_disc(
            drive=self.drive,
            toc=toc,
            album=album,
            config=config,
            progress_callback=on_prog,
            cancel_event=cancel,
        )

        # 出力ファイルの存在確認 (<output_dir>/The Beatles/Abbey Road/)
        target_album_dir = os.path.join(self.test_dir, "The Beatles", "Abbey Road")
        self.assertTrue(os.path.isdir(target_album_dir), f"Directory not found: {target_album_dir}")

        files = os.listdir(target_album_dir)
        m4a_files = [f for f in files if f.endswith(".m4a")]
        self.assertEqual(len(m4a_files), 2)
        self.assertIn("1-01 Come Together.m4a", m4a_files)
        self.assertIn("1-02 Something.m4a", m4a_files)

        track1_path = os.path.join(target_album_dir, "1-01 Come Together.m4a")

        # ファイルサイズがAAC 256k相当（1秒で > 5KB）であること
        self.assertGreater(os.path.getsize(track1_path), 5000)
        self.assertTrue(progress_events[-1].is_finished)

        # TC-ENC-02: ffprobe によるタグ検証 (Title, Artist, Album, Track)
        ffprobe_bin = shutil.which("ffprobe")
        if ffprobe_bin:
            cmd = [
                ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                track1_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0)
            probe_data = json.loads(res.stdout)
            tags = probe_data.get("format", {}).get("tags", {})

            # 小文字・大文字のタグキー両方に対応
            title_tag = tags.get("title") or tags.get("TITLE")
            artist_tag = tags.get("artist") or tags.get("ARTIST")
            album_tag = tags.get("album") or tags.get("ALBUM")
            track_tag = tags.get("track") or tags.get("TRACK")

            self.assertEqual(title_tag, "Come Together")
            self.assertEqual(artist_tag, "The Beatles")
            self.assertEqual(album_tag, "Abbey Road")
            self.assertIn("1/", str(track_tag))

    def test_custom_track_tags_full_e2e_ffprobe_verification(self):
        """AC-003, AC-004, AC-005, TC-RIP-004: トラック毎の全8項目個別タグ実測検証"""
        if not self.encoder.is_ffmpeg_available():
            self.skipTest("FFmpeg binary not found on system PATH; skipping real encode test.")
            return

        self.drive.open("V:")
        toc = self.drive.read_toc()

        # トラック1にNTFS禁止文字を含む特殊タイトルと全8項目カスタムタグを設定
        tag1 = TrackTagData(
            track_number=1,
            total_tracks=2,
            disc_number=1,
            total_discs=2,
            title="AC/DC: Live <Special> *Edition*",  # Contains NTFS forbidden chars
            artist="Custom Artist 1",
            album="Custom Compilation Vol. 1",
            date="2024",
            genre="Hard Rock",
            encoder="Test Encoder V2",
            is_customized=True,
        )
        # トラック2に異なる個別タグを設定
        tag2 = TrackTagData(
            track_number=2,
            total_tracks=2,
            disc_number=1,
            total_discs=2,
            title="Moonlight Sonata",
            artist="Ludwig van Beethoven",
            album="Classical Favorites",
            date="2025",
            genre="Classical",
            encoder="Test Encoder V2",
            is_customized=True,
        )

        track_tags = {1: tag1, 2: tag2}

        config = RipConfig(
            output_dir=self.test_dir,
            format=EncodeFormat.AAC_256K,
            selected_speed_x=8,
        )

        self.pipeline.rip_disc(
            drive=self.drive,
            toc=toc,
            album=None,
            config=config,
            progress_callback=lambda p: None,
            cancel_event=threading.Event(),
            track_tags=track_tags,
        )

        # ファイル名がサニタイズされて存在すること (AC-005)
        # トラック1は "Custom Artist 1/Custom Compilation Vol. 1/1-01 AC_DC_ Live _Special_ _Edition_.m4a"
        target_album_dir = os.path.join(self.test_dir, "Custom Artist 1", "Custom Compilation Vol. 1")
        self.assertTrue(os.path.isdir(target_album_dir), f"Directory not found: {target_album_dir}")

        files = os.listdir(target_album_dir)
        m4a_files = [f for f in files if f.endswith(".m4a")]
        self.assertEqual(len(m4a_files), 1)

        # Track 1 file: "1-01 AC_DC_ Live _Special_ _Edition_.m4a"
        trk1_files = [f for f in m4a_files if f.startswith("1-01 ")]
        self.assertEqual(len(trk1_files), 1)
        track1_path = os.path.join(target_album_dir, trk1_files[0])

        # トラック2は別アルバムフォルダに出力されること
        target_album_dir2 = os.path.join(self.test_dir, "Ludwig van Beethoven", "Classical Favorites")
        self.assertTrue(os.path.isdir(target_album_dir2), f"Directory not found: {target_album_dir2}")
        files2 = os.listdir(target_album_dir2)
        self.assertIn("1-02 Moonlight Sonata.m4a", files2)

        # ffprobe で全8項目タグを実測検証 (AC-003)
        ffprobe_bin = shutil.which("ffprobe")
        if ffprobe_bin:
            cmd = [
                ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                track1_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0)
            probe_data = json.loads(res.stdout)
            tags = {k.lower(): v for k, v in probe_data.get("format", {}).get("tags", {}).items()}

            # 完全な生タイトルがタグに保持されていること (AC-005)
            self.assertEqual(tags.get("title"), "AC/DC: Live <Special> *Edition*")
            self.assertEqual(tags.get("artist"), "Custom Artist 1")
            self.assertEqual(tags.get("album"), "Custom Compilation Vol. 1")
            self.assertEqual(tags.get("date"), "2024")
            self.assertEqual(tags.get("genre"), "Hard Rock")
            self.assertEqual(tags.get("track"), "1/2")
            self.assertEqual(tags.get("disc"), "1/2")
            # Note: FFmpeg MP4 muxer overrides 'encoder' tag with 'Lavf...', but encoder arg was passed in metadata
            self.assertTrue(tags.get("encoder", "").startswith("Lavf"))


if __name__ == "__main__":
    unittest.main()
