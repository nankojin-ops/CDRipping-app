"""Unit tests for iTunes API client and metadata parsing (TC-MET-01 - TC-MET-08)."""
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from cdripper.domain.exceptions import MetadataNetworkError
from cdripper.domain.models import AlbumMetadata, DiscTOC, TrackMetadata, TrackTOC
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.metadata.mock_provider import MockMetadataProvider


class TestITunesClient(unittest.TestCase):
    def setUp(self):
        self.client = ITunesApiClient(timeout=5)

    def test_highres_artwork_url_regex(self):
        """TC-MET-02: 高解像度アートワークURL正規表現置換 (1200x1200bb)"""
        url1 = "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/60x60bb.jpg"
        highres1 = ITunesApiClient.get_highres_artwork_url(url1, 1200)
        self.assertEqual(highres1, "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/1200x1200bb.jpg")

        url2 = "https://example.com/art/500x500bb.png"
        highres2 = ITunesApiClient.get_highres_artwork_url(url2, 1200)
        self.assertEqual(highres2, "https://example.com/art/1200x1200bb.png")

    def test_multidisc_filter(self):
        """TC-MET-03: マルチディスク (discNumber) 絞り込み"""
        album = AlbumMetadata(
            collection_id=1,
            album_name="Double Album",
            artist_name="Artist",
            release_year="2020",
            genre="Pop",
            total_tracks=3,
            total_discs=2,
            tracks=[
                TrackMetadata(1, "D1 Track 1", "Artist", 180000, 1),
                TrackMetadata(2, "D1 Track 2", "Artist", 200000, 1),
                TrackMetadata(1, "D2 Track 1", "Artist", 210000, 2),
            ],
        )
        disc1_tracks = ITunesApiClient.filter_tracks_by_disc(album, 1)
        self.assertEqual(len(disc1_tracks), 2)
        self.assertEqual(disc1_tracks[0].track_title, "D1 Track 1")

        disc2_tracks = ITunesApiClient.filter_tracks_by_disc(album, 2)
        self.assertEqual(len(disc2_tracks), 1)
        self.assertEqual(disc2_tracks[0].track_title, "D2 Track 1")

    def test_match_tracks_with_toc_normal(self):
        """正常系のTOCマッチング"""
        toc = DiscTOC(
            first_track=1,
            last_track=2,
            total_tracks=2,
            total_duration_seconds=7.0,
            tracks=[
                TrackTOC(1, 0, 225, 225, 3.0, True),
                TrackTOC(2, 225, 525, 300, 4.0, True),
            ],
        )
        album = AlbumMetadata(
            collection_id=1,
            album_name="Test",
            artist_name="Test Artist",
            release_year="2020",
            genre="Rock",
            total_tracks=2,
            tracks=[
                TrackMetadata(1, "Track 1", "Test Artist", 3000, 1),
                TrackMetadata(2, "Track 2", "Test Artist", 4000, 1),
            ],
        )
        matched, is_complete = ITunesApiClient.match_tracks_with_toc(toc, album, 1)
        self.assertTrue(is_complete)
        self.assertEqual(len(matched), 2)
        self.assertEqual(matched[0][1].track_title, "Track 1")

    def test_match_tracks_with_toc_mismatch(self):
        """TC-MET-04 (境界値): トラック数不一致および演奏時間4秒超の差分で is_complete == False"""
        # トラック数不一致 (CD: 2曲 vs iTunes: 3曲)
        toc = DiscTOC(
            first_track=1,
            last_track=2,
            total_tracks=2,
            total_duration_seconds=7.0,
            tracks=[
                TrackTOC(1, 0, 225, 225, 3.0, True),
                TrackTOC(2, 225, 525, 300, 4.0, True),
            ],
        )
        album_3tracks = AlbumMetadata(
            collection_id=1,
            album_name="Test",
            artist_name="Test Artist",
            release_year="2020",
            genre="Rock",
            total_tracks=3,
            tracks=[
                TrackMetadata(1, "Track 1", "Test Artist", 3000, 1),
                TrackMetadata(2, "Track 2", "Test Artist", 4000, 1),
                TrackMetadata(3, "Track 3", "Test Artist", 5000, 1),
            ],
        )
        matched, is_complete = ITunesApiClient.match_tracks_with_toc(toc, album_3tracks, 1)
        self.assertFalse(is_complete)

        # 演奏時間の差が4秒を超える場合 (CD: 3.0s vs iTunes: 10.0s)
        album_diff_duration = AlbumMetadata(
            collection_id=1,
            album_name="Test",
            artist_name="Test Artist",
            release_year="2020",
            genre="Rock",
            total_tracks=2,
            tracks=[
                TrackMetadata(1, "Track 1", "Test Artist", 10000, 1),  # 10s vs 3s
                TrackMetadata(2, "Track 2", "Test Artist", 4000, 1),
            ],
        )
        matched, is_complete = ITunesApiClient.match_tracks_with_toc(
            toc, album_diff_duration, 1, tolerance_seconds=4.0
        )
        self.assertFalse(is_complete)

    def test_search_zero_results(self):
        """TC-MET-05: 検索結果0件ハンドリング"""
        # 空文字列検索
        empty_res = self.client.search_albums("")
        self.assertEqual(empty_res, [])

        # APIが結果0件を返した場合
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"resultCount": 0, "results": []}'
            mock_url.return_value.__enter__.return_value = mock_resp

            results = self.client.search_albums("NonExistentAlbumXYZ123456")
            self.assertEqual(results, [])

    def test_parse_album_item_missing_fields(self):
        """TC-MET-08 (欠損値): releaseDateやprimaryGenreNameが欠損したレスポンスの耐性"""
        raw_item = {
            "wrapperType": "collection",
            "collectionId": 9999,
            "collectionName": "Sparse Album",
            "artistName": "Sparse Artist",
            # releaseDate, primaryGenreName, artworkUrl100 missing or None
        }
        album = self.client._parse_album_item(raw_item)
        self.assertEqual(album.collection_id, 9999)
        self.assertEqual(album.album_name, "Sparse Album")
        self.assertEqual(album.release_year, "Unknown Year")
        self.assertEqual(album.genre, "Unknown Genre")
        self.assertIsNone(album.artwork_url)

    def test_network_error_handling(self):
        """TC-MET-06 (異常系): 通信障害・タイムアウト時に MetadataNetworkError が送出されること"""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
            with self.assertRaises(MetadataNetworkError):
                self.client.search_albums("Abbey Road")

    def test_mock_metadata_provider(self):
        """MockMetadataProvider の基本動作検証"""
        mock_prov = MockMetadataProvider()
        results = mock_prov.search_albums("Abbey Road")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].album_name, "Abbey Road")

        artwork = mock_prov.download_artwork("https://example.com/art.jpg")
        self.assertIsNotNone(artwork)
        self.assertTrue(artwork.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
