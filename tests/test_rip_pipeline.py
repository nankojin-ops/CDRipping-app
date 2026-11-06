"""Unit tests for AudioRipPipeline and sector boundary reading (FINDING-006, TC-RIP-01, TC-RIP-03)."""
import os
import threading
import unittest
from unittest.mock import MagicMock

from cdripper.domain.models import (
    AlbumMetadata,
    DiscTOC,
    RipConfig,
    TrackTagData,
    TrackTOC,
)
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.pipeline.rip_pipeline import (
    AudioRipPipeline,
    read_track_sectors,
    resolve_track_output_path,
)


class TestRipPipeline(unittest.TestCase):
    def test_sector_boundary_calculation(self):
        # 187 sectors: 75 + 75 + 37 (not a multiple of 75)
        track = TrackTOC(
            track_number=1,
            start_lba=100,
            end_lba=287,
            sector_count=187,
            duration_seconds=187 / 75.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)

        read_track_sectors(drive, track, on_chunk, batch_size=75)

        # Expected chunks: 75*2352, 75*2352, 37*2352
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 75 * 2352)
        self.assertEqual(len(chunks[1]), 75 * 2352)
        self.assertEqual(len(chunks[2]), 37 * 2352)

    def test_cancel_token_stops_reading(self):
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=1500,
            sector_count=1500,
            duration_seconds=20.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        token = threading.Event()
        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)
            token.set()  # Stop after 1 chunk

        read_track_sectors(drive, track, on_chunk, cancel_token=token, batch_size=75)
        self.assertEqual(len(chunks), 1)

    def test_read_track_sectors_default_batch_size_25(self):
        """TASK-006: batch_size省略時にデフォルト25セクタ単位でコールバックが呼ばれること"""
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=75,
            sector_count=75,
            duration_seconds=1.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        chunks = []
        def on_chunk(chunk: bytes):
            chunks.append(chunk)

        read_track_sectors(drive, track, on_chunk)  # batch_size omitted

        # 75 sectors with default batch_size=25 -> 3 chunks of 25 sectors
        self.assertEqual(len(chunks), 3)
        for chunk in chunks:
            self.assertEqual(len(chunk), 25 * 2352)



    def test_read_track_sectors_invalid_batch_size(self):
        """SEC-PIPE-001: batch_size <= 0 で ValueError が送出されること"""
        track = TrackTOC(
            track_number=1,
            start_lba=0,
            end_lba=75,
            sector_count=75,
            duration_seconds=1.0,
            is_audio=True,
        )
        drive = VirtualCDDrive()
        drive.open("V:")

        with self.assertRaises(ValueError):
            read_track_sectors(drive, track, lambda chunk: None, batch_size=0)

        with self.assertRaises(ValueError):
            read_track_sectors(drive, track, lambda chunk: None, batch_size=-5)


    def test_rip_pipeline_embeds_album_artist_and_artwork(self):
        """TC-AC005-01, TC-AC005-02: Verifies album_artist and artwork are passed to encoder session."""
        mock_encoder = MagicMock()
        mock_encoder.start_encoding_session.return_value = MagicMock()

        pipeline = AudioRipPipeline(encoder=mock_encoder)
        drive = VirtualCDDrive(track_durations=[2])
        toc = DiscTOC(1, 1, 1, 2.0, [TrackTOC(1, 0, 150, 150, 2.0, True)])

        art_data = b"image_bytes_here"
        album = AlbumMetadata(
            collection_id=1,
            album_name="Test Album",
            artist_name="Test Artist",
            album_artist="Album Artist Name",
            release_year="2026",
            genre="Pop",
            total_tracks=1,
            artwork_data=art_data,
        )

        track_tags = {
            1: TrackTagData(
                track_number=1,
                total_tracks=1,
                disc_number=1,
                total_discs=1,
                title="Track 01",
                artist="Soloist",
                album_artist="Album Artist Name",
                album="Test Album",
                date="2026",
                genre="Pop",
            )
        }

        config = RipConfig(output_dir="test_out")
        cb = MagicMock()
        cancel_evt = MagicMock()
        cancel_evt.is_set.return_value = False

        pipeline.rip_disc(
            drive=drive,
            toc=toc,
            album=album,
            config=config,
            progress_callback=cb,
            cancel_event=cancel_evt,
            track_tags=track_tags,
        )

        mock_encoder.start_encoding_session.assert_called_once()
        call_kwargs = mock_encoder.start_encoding_session.call_args[1]
        self.assertEqual(call_kwargs["track_metadata"]["album_artist"], "Album Artist Name")
        self.assertEqual(call_kwargs["artwork_bytes"], art_data)





class TestResolveTrackOutputPath(unittest.TestCase):
    """Unit tests for resolve_track_output_path and collision avoidance (AC-001..AC-005, CHALLENGE-001..005)."""

    def setUp(self):
        self.base_dir = r"C:\Music\Output"

    def test_resolve_normal(self):
        """TC-HP-001, AC-001, AC-004: 標準的な単一ディスクCDのリッピングパス生成"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=1,
            track_title="Come Together",
            album_artist="The Beatles",
            album_name="Abbey Road",
            ext=".m4a",
        )
        expected = os.path.join(self.base_dir, "The Beatles", "Abbey Road", "1-01 Come Together.m4a")
        self.assertEqual(path, expected)

    def test_disc_number_reflected_in_filename(self):
        """TC-HP-002, AC-004, AC-005: 複数枚組CD（Disc 2以降）のパス生成とCD番号反映"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=2,
            track_number=5,
            track_title="Comfortably Numb",
            album_artist="Pink Floyd",
            album_name="The Wall",
            ext=".flac",
        )
        expected = os.path.join(self.base_dir, "Pink Floyd", "The Wall", "2-05 Comfortably Numb.flac")
        self.assertEqual(path, expected)

    def test_multibyte_japanese_tags(self):
        """TC-HP-003, AC-001, AC-003, AC-004: 日本語マルチバイトタグの処理"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=3,
            track_title="紅蓮華",
            album_artist="LiSA",
            album_name="LEO-NiNE",
            ext=".m4a",
        )
        expected = os.path.join(self.base_dir, "LiSA", "LEO-NiNE", "1-03 紅蓮華.m4a")
        self.assertEqual(path, expected)

    def test_custom_template(self):
        """TC-HP-004: カスタムテンプレートの利用"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=7,
            track_title="Track Name",
            album_artist="Artist",
            album_name="Album",
            filename_template="CD{disc_number}_{track_num:03d}_{title}{ext}",
        )
        expected = os.path.join(self.base_dir, "Artist", "Album", "CD1_007_Track Name.m4a")
        self.assertEqual(path, expected)

    def test_custom_template_backward_compatibility(self):
        """FR-002: 旧テンプレート（disc_numberなし）の後方互換性"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=2,
            track_title="Song",
            album_artist="Artist",
            album_name="Album",
            filename_template="{track_num:02d} - {title}{ext}",
        )
        expected = os.path.join(self.base_dir, "Artist", "Album", "02 - Song.m4a")
        self.assertEqual(path, expected)

    def test_extension_variations(self):
        """TC-HP-005: 拡張子のドット有無・大文字小文字"""
        path1 = resolve_track_output_path(
            self.base_dir, 1, 1, "Song", "Artist", "Album", ext="mp3"
        )
        self.assertTrue(path1.endswith("1-01 Song.mp3"))

        path2 = resolve_track_output_path(
            self.base_dir, 1, 1, "Song", "Artist", "Album", ext=".FLAC"
        )
        self.assertTrue(path2.endswith("1-01 Song.FLAC"))

    def test_fallback_empty_artist_and_album(self):
        """TC-NEG-001, AC-002, CHALLENGE-002: 空文字・空白時の Unknown Artist / Unknown Album フォールバック"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=1,
            track_title="Song",
            album_artist="",
            album_name="   ",
        )
        expected = os.path.join(self.base_dir, "Unknown Artist", "Unknown Album", "1-01 Song.m4a")
        self.assertEqual(path, expected)

    def test_fallback_none_artist_and_album(self):
        """TC-NEG-001, AC-002: None 時の Unknown Artist / Unknown Album フォールバック"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=1,
            track_title="Song",
            album_artist=None,
            album_name=None,
        )
        expected = os.path.join(self.base_dir, "Unknown Artist", "Unknown Album", "1-01 Song.m4a")
        self.assertEqual(path, expected)

    def test_fallback_explicit_unknown(self):
        """TC-NEG-002, CHALLENGE-002: 'Unknown' 指定時の明示的フォールバック正規化"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=1,
            track_title="Song",
            album_artist="Unknown",
            album_name="Unknown",
        )
        expected = os.path.join(self.base_dir, "Unknown Artist", "Unknown Album", "1-01 Song.m4a")
        self.assertEqual(path, expected)

    def test_fallback_empty_or_none_title(self):
        """TC-NEG-003: タイトル空・None・Unknown 時に Track {trk_num:02d} にフォールバック"""
        path1 = resolve_track_output_path(self.base_dir, 1, 4, "", "Artist", "Album")
        self.assertTrue(path1.endswith("1-04 Track 04.m4a"))

        path2 = resolve_track_output_path(self.base_dir, 1, 4, None, "Artist", "Album")
        self.assertTrue(path2.endswith("1-04 Track 04.m4a"))

        path3 = resolve_track_output_path(self.base_dir, 1, 4, "Unknown", "Artist", "Album")
        self.assertTrue(path3.endswith("1-04 Track 04.m4a"))

    def test_invalid_disc_and_track_numbers(self):
        """TC-NEG-004, TC-NEG-005, CHALLENGE-005: 不正な disc_number / track_number 入力の安全化"""
        path1 = resolve_track_output_path(self.base_dir, disc_number=-1, track_number=0, track_title="Song")
        self.assertTrue(path1.endswith("1-01 Song.m4a"))

        path2 = resolve_track_output_path(self.base_dir, disc_number="abc", track_number=None, track_title="Song")
        self.assertTrue(path2.endswith("1-01 Song.m4a"))

    def test_invalid_template_syntax_fallback(self):
        """TC-NEG-006, CHALLENGE-005: 壊れたテンプレート構文での例外クラッシュ防止"""
        path = resolve_track_output_path(
            self.base_dir, 1, 1, "Song",
            filename_template="{disc_number}-{track_num:02d} {invalid_key}{ext}"
        )
        self.assertTrue(path.endswith("1-01 Song.m4a"))

    def test_forbidden_chars_sanitization(self):
        """TC-NEG-007, AC-003: NTFS禁止文字のみで構成されたタグのフォールバックと安全化"""
        path = resolve_track_output_path(
            self.base_dir, 1, 1, "Song?",
            album_artist=": * ? < > |",
            album_name="/ / \\",
        )
        expected = os.path.join(self.base_dir, "Unknown Artist", "Unknown Album", "1-01 Song_.m4a")
        self.assertEqual(path, expected)

    def test_path_traversal_relative_parent_dots(self):
        """TC-SEC-001, AC-003, CHALLENGE-001: 相対パストラバーサル (../) 防御"""
        path = resolve_track_output_path(
            self.base_dir, 1, 1, "Song",
            album_artist="../../Windows/System32",
            album_name="..\\..\\Escape",
        )
        abs_base = os.path.normcase(os.path.abspath(self.base_dir))
        abs_target = os.path.normcase(os.path.abspath(path))
        self.assertTrue(abs_target.startswith(abs_base))

    def test_path_traversal_absolute_path(self):
        """TC-SEC-002, CHALLENGE-001: 絶対パス挿入攻撃の防御"""
        path = resolve_track_output_path(
            self.base_dir, 1, 1, "Song",
            album_artist="C:\\RootAttack",
            album_name="/etc/shadow",
        )
        abs_base = os.path.normcase(os.path.abspath(self.base_dir))
        abs_target = os.path.normcase(os.path.abspath(path))
        self.assertTrue(abs_target.startswith(abs_base))

    def test_max_component_length_truncation(self):
        """TC-BND-003, CHALLENGE-004: max_component_length=60 によるコンポーネント切り詰め"""
        long_name = "A" * 100
        path = resolve_track_output_path(
            self.base_dir, 1, 1, long_name,
            album_artist=long_name,
            album_name=long_name,
            max_component_length=60,
        )
        parts = path.split(os.sep)
        artist_dir = parts[-3]
        album_dir = parts[-2]
        file_name, _ = os.path.splitext(parts[-1])
        self.assertLessEqual(len(artist_dir), 60)
        self.assertLessEqual(len(album_dir), 60)
        self.assertLessEqual(len(file_name), 60)

    def test_collision_avoidance_with_existing_file_on_disk(self):
        """TC-COL-002, CHALLENGE-003: ディスク上の既存ファイルとの衝突回避"""
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp(prefix="cdrip_col_test_")
        try:
            target_dir = os.path.join(temp_dir, "Artist", "Album")
            os.makedirs(target_dir, exist_ok=True)
            existing_file = os.path.join(target_dir, "1-01 Track.m4a")
            with open(existing_file, "w") as f:
                f.write("dummy")

            base_output_path = resolve_track_output_path(
                temp_dir, 1, 1, "Track", "Artist", "Album", ext=".m4a"
            )
            self.assertEqual(base_output_path, existing_file)

            seen_paths = set()
            output_path = base_output_path
            if output_path in seen_paths or os.path.exists(output_path):
                base, fext = os.path.splitext(output_path)
                collision_idx = 1
                candidate = f"{base}_{collision_idx}{fext}"
                while candidate in seen_paths or os.path.exists(candidate):
                    collision_idx += 1
                    candidate = f"{base}_{collision_idx}{fext}"
                output_path = candidate
            seen_paths.add(output_path)

            self.assertEqual(output_path, os.path.join(target_dir, "1-01 Track_1.m4a"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    def test_custom_template_track_number_alias(self):
        """FIND-CR-003: {track_number} エイリアスのサポート"""
        path = resolve_track_output_path(
            base_output_dir=self.base_dir,
            disc_number=1,
            track_number=8,
            track_title="Song",
            album_artist="Artist",
            album_name="Album",
            filename_template="{disc_number}-{track_number:02d} {title}{ext}",
        )
        expected = os.path.join(self.base_dir, "Artist", "Album", "1-08 Song.m4a")
        self.assertEqual(path, expected)

    def test_deep_base_dir_max_path_guard(self):
        """FIND-SEC-012, TC-BND-004: 深層ベースディレクトリ時の MAX_PATH (260文字) ガード"""
        deep_base = "C:\\" + ("sub\\" * 35)  # 約140文字
        path = resolve_track_output_path(
            base_output_dir=deep_base,
            disc_number=1,
            track_number=1,
            track_title="A" * 80,
            album_artist="B" * 80,
            album_name="C" * 80,
        )
        self.assertLessEqual(len(os.path.abspath(path)), 255)

    def test_rip_disc_avoids_collision_with_existing_file_on_disk(self):
        """FIND-SEC-013, FIND-CR-002, TC-COL-002: AudioRipPipeline.rip_disc 経由の実結合衝突回避"""
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp(prefix="cdrip_disc_col_")
        try:
            # 既存ファイルを事前に配置: <temp_dir>/Test Artist/Test Album/1-01 Track 01.m4a
            target_album_dir = os.path.join(temp_dir, "Test Artist", "Test Album")
            os.makedirs(target_album_dir, exist_ok=True)
            existing_file = os.path.join(target_album_dir, "1-01 Track 01.m4a")
            with open(existing_file, "w") as f:
                f.write("existing audio")

            mock_encoder = MagicMock()
            mock_encoder.start_encoding_session.return_value = MagicMock()

            pipeline = AudioRipPipeline(encoder=mock_encoder)
            drive = VirtualCDDrive(track_durations=[2])
            toc = DiscTOC(1, 1, 1, 2.0, [TrackTOC(1, 0, 150, 150, 2.0, True)])
            album = AlbumMetadata(
                collection_id=1,
                album_name="Test Album",
                artist_name="Test Artist",
                release_year="2026",
                genre="Pop",
                total_tracks=1,
            )
            config = RipConfig(output_dir=temp_dir)
            cancel_evt = MagicMock()
            cancel_evt.is_set.return_value = False

            pipeline.rip_disc(
                drive=drive,
                toc=toc,
                album=album,
                config=config,
                progress_callback=MagicMock(),
                cancel_event=cancel_evt,
            )

            mock_encoder.start_encoding_session.assert_called_once()
            call_kwargs = mock_encoder.start_encoding_session.call_args[1]
            actual_output = call_kwargs["output_path"]
            # 既存ファイルが _1.m4a に回避されていることを実証
            expected_output = os.path.join(target_album_dir, "1-01 Track 01_1.m4a")
            self.assertEqual(actual_output, expected_output)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
