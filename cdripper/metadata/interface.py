"""Abstract base class interface for metadata providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from cdripper.domain.models import AlbumMetadata


class IMetadataProvider(ABC):
    """Interface for fetching CD album metadata and cover artwork."""

    @abstractmethod
    def search_albums(self, query: str, country: str = "jp", limit: int = 10) -> List[AlbumMetadata]:
        """Search albums by title or artist keyword."""
        raise NotImplementedError

    @abstractmethod
    def lookup_album_tracks(self, collection_id: int, country: str = "jp") -> AlbumMetadata:
        """Lookup complete track list for a specific album collection ID."""
        raise NotImplementedError

    @abstractmethod
    def download_artwork(self, artwork_url: str, size: int = 1200) -> Optional[bytes]:
        """Download high-resolution cover artwork image."""
        raise NotImplementedError