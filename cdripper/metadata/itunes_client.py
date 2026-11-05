"""iTunes Search and Lookup API client implementation."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

from cdripper.domain.exceptions import MetadataNetworkError, MetadataNotFoundError
from cdripper.domain.models import AlbumMetadata, DiscTOC, TrackMetadata, TrackTOC
from cdripper.metadata.interface import IMetadataProvider


class ITunesApiClient(IMetadataProvider):
    """Client for querying Apple iTunes Search / Lookup APIs."""

    SEARCH_URL = "https://itunes.apple.com/search"
    LOOKUP_URL = "https://itunes.apple.com/lookup"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def search_albums(self, query: str, country: str = "jp", limit: int = 10) -> List[AlbumMetadata]:
        """Search iTunes for albums matching the query string."""
        if not query or not query.strip():
            return []

        params = {
            "term": query.strip(),
            "entity": "album",
            "country": country,
            "limit": limit,
        }
        url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CDRippingApp/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise MetadataNetworkError(f"iTunes Search API network error: {e}")
        except Exception as e:
            raise MetadataNetworkError(f"Failed to parse iTunes search response: {e}")

        results = data.get("results", [])
        albums: List[AlbumMetadata] = []

        for item in results:
            if item.get("wrapperType") == "collection":
                album = self._parse_album_item(item)
                albums.append(album)

        return albums

    def lookup_album_tracks(self, collection_id: int, country: str = "jp") -> AlbumMetadata:
        """Lookup album and its tracks using collection ID."""
        params = {
            "id": collection_id,
            "entity": "song",
            "country": country,
        }
        url = f"{self.LOOKUP_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CDRippingApp/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise MetadataNetworkError(f"iTunes Lookup API network error: {e}")
        except Exception as e:
            raise MetadataNetworkError(f"Failed to parse iTunes lookup response: {e}")

        results = data.get("results", [])
        if not results:
            raise MetadataNotFoundError(f"No album found for collection ID {collection_id}")

        collection_item = results[0]
        album = self._parse_album_item(collection_item)

        tracks: List[TrackMetadata] = []
        max_disc = 1

        for item in results[1:]:
            if item.get("wrapperType") == "track":
                disc_num = item.get("discNumber", 1)
                if disc_num > max_disc:
                    max_disc = disc_num
                track = TrackMetadata(
                    track_number=item.get("trackNumber", len(tracks) + 1),
                    track_title=item.get("trackName", f"Track {len(tracks) + 1}"),
                    artist_name=item.get("artistName", album.artist_name),
                    duration_millis=item.get("trackTimeMillis", 0),
                    disc_number=disc_num,
                )
                tracks.append(track)

        album.total_discs = max_disc
        album.tracks = tracks
        return album

    def download_artwork(self, artwork_url: str, size: int = 1200) -> Optional[bytes]:
        """Download album artwork with high-resolution URL replacement."""
        if not artwork_url:
            return None

        highres_url = self.get_highres_artwork_url(artwork_url, size=size)

        try:
            req = urllib.request.Request(highres_url, headers={"User-Agent": "CDRippingApp/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except Exception:
            if highres_url != artwork_url:
                try:
                    req = urllib.request.Request(artwork_url, headers={"User-Agent": "CDRippingApp/1.0"})
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        return resp.read()
                except Exception:
                    pass
            return None

    @staticmethod
    def get_highres_artwork_url(artwork_url: str, size: int = 1200) -> str:
        """Replace low-resolution pattern in iTunes artwork URL with high-res size."""
        if not artwork_url:
            return ""
        return re.sub(r"\d+x\d+bb\.", f"{size}x{size}bb.", artwork_url)

    @staticmethod
    def filter_tracks_by_disc(album: AlbumMetadata, disc_number: int = 1) -> List[TrackMetadata]:
        """Filter tracks belonging to a specific disc number, sorted by track number."""
        disc_tracks = [t for t in album.tracks if t.disc_number == disc_number]
        disc_tracks.sort(key=lambda t: t.track_number)
        return disc_tracks

    @staticmethod
    def match_tracks_with_toc(
        toc: DiscTOC,
        album: AlbumMetadata,
        disc_number: int = 1,
        tolerance_seconds: float = 4.0,
    ) -> Tuple[List[Tuple[TrackTOC, Optional[TrackMetadata]]], bool]:
        """
        Match CD TOC tracks with iTunes tracks for the given disc.
        Returns (matched_list, is_complete_match).
        """
        disc_tracks = ITunesApiClient.filter_tracks_by_disc(album, disc_number)
        matched: List[Tuple[TrackTOC, Optional[TrackMetadata]]] = []
        is_complete = True

        if len(toc.tracks) != len(disc_tracks):
            is_complete = False

        track_dict = {t.track_number: t for t in disc_tracks}

        for toc_track in toc.tracks:
            itunes_track = track_dict.get(toc_track.track_number)
            if itunes_track:
                itunes_sec = itunes_track.duration_millis / 1000.0
                if abs(toc_track.duration_seconds - itunes_sec) > tolerance_seconds:
                    is_complete = False
                matched.append((toc_track, itunes_track))
            else:
                matched.append((toc_track, None))
                is_complete = False

        return matched, is_complete

    def _parse_album_item(self, item: dict) -> AlbumMetadata:
        """Parse raw JSON collection dictionary safely with defaults."""
        release_date = item.get("releaseDate", "")
        year = release_date[:4] if release_date else ""

        return AlbumMetadata(
            collection_id=item.get("collectionId", 0),
            album_name=item.get("collectionName", "Unknown Album"),
            artist_name=item.get("artistName", "Unknown Artist"),
            release_year=year or "Unknown Year",
            genre=item.get("primaryGenreName", "Unknown Genre"),
            total_tracks=item.get("trackCount", 0),
            artwork_url=item.get("artworkUrl100"),
        )