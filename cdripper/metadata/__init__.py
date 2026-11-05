"""Metadata layer for iTunes Search/Lookup and mock providers."""
from cdripper.metadata.interface import IMetadataProvider
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.metadata.mock_provider import MockMetadataProvider

__all__ = [
    "IMetadataProvider",
    "ITunesApiClient",
    "MockMetadataProvider",
]