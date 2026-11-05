"""End-to-End integration test across VirtualCDDrive -> MockMetadata -> RipPipeline (TC-MCK-02, TC-ENC-02)."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

from cdripper.domain.models import EncodeFormat, RipConfig
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

        # 出力ファイルの存在確認
        files = os.listdir(self.test_dir)
        m4a_files = [f for f in files if f.endswith(".m4a")]
        self.assertEqual(len(m4a_files), 2)
        track1_file = [f for f in m4a_files if "Come Together" in f][0]
        track1_path = os.path.join(self.test_dir, track1_file)

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


if __name__ == "__main__":
    unittest.main()
