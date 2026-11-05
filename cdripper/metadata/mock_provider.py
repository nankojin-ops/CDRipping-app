"""Mock metadata provider for offline testing and CI."""
from __future__ import annotations

from typing import List, Optional

from cdripper.domain.models import AlbumMetadata, TrackMetadata
from cdripper.metadata.interface import IMetadataProvider


class MockMetadataProvider(IMetadataProvider):
    """In-memory mock metadata provider for reliable regression testing."""

    def __init__(self):
        self.sample_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00"
            b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.albums = self._init_sample_albums()

    def _init_sample_albums(self) -> List[AlbumMetadata]:
        album1 = AlbumMetadata(
            collection_id=1001,
            album_name="Abbey Road",
            artist_name="The Beatles",
            release_year="1969",
            genre="Rock",
            total_tracks=3,
            total_discs=1,
            artwork_url="https://example.com/artwork/100x100bb.jpg",
            tracks=[
                TrackMetadata(1, "Come Together", "The Beatles", 3000, 1),
                TrackMetadata(2, "Something", "The Beatles", 4000, 1),
                TrackMetadata(3, "Maxwell's Silver Hammer", "The Beatles", 3000, 1),
            ],
        )

        album2_multidisc = AlbumMetadata(
            collection_id=1002,
            album_name="The White Album",
            artist_name="The Beatles",
            release_year="1968",
            genre="Rock",
            total_tracks=4,
            total_discs=2,
            artwork_url="https://example.com/artwork/white_100x100bb.jpg",
            tracks=[
                TrackMetadata(1, "Back in the U.S.S.R.", "The Beatles", 3000, 1),
                TrackMetadata(2, "Dear Prudence", "The Beatles", 4000, 1),
                TrackMetadata(1, "Birthday", "The Beatles", 3000, 2),
                TrackMetadata(2, "Yer Blues", "The Beatles", 4000, 2),
            ],
        )

        return [album1, album2_multidisc]

    def search_albums(self, query: str, country: str = "jp", limit: int = 10) -> List[AlbumMetadata]:
        q = query.lower().strip()
        results = [
            a for a in self.albums
            if q in a.album_name.lower() or q in a.artist_name.lower()
        ]
        return results[:limit]

    def lookup_album_tracks(self, collection_id: int, country: str = "jp") -> AlbumMetadata:
        for a in self.albums:
            if a.collection_id == collection_id:
                return a
        return AlbumMetadata(
            collection_id=collection_id,
            album_name="Unknown Album",
            artist_name="Unknown Artist",
            release_year="2026",
            genre="Pop",
            total_tracks=1,
            tracks=[TrackMetadata(1, "Track 1", "Unknown Artist", 3000, 1)],
        )

    def download_artwork(self, artwork_url: str, size: int = 1200) -> Optional[bytes]:
        if "404" in artwork_url:
            return None
        return self.sample_png