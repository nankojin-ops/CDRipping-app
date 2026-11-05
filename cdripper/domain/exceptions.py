"""Custom exceptions for CD Ripper Application."""


class CDRipperError(Exception):
    """Base exception for all CD Ripper errors."""
    pass


class CDDriveError(CDRipperError):
    """Base exception for CD drive hardware operations."""
    pass


class CDDriveNotFoundError(CDDriveError):
    """Raised when no optical CD/DVD drives are detected."""
    pass


class CDDriveNoMediaError(CDDriveError):
    """Raised when the specified drive has no disc inserted."""
    pass


class CDDriveAccessDeniedError(CDDriveError):
    """Raised when Windows OS denies raw access to the optical drive (e.g. UAC restriction)."""
    pass


class CDDriveReadError(CDDriveError):
    """Raised when reading sectors from the disc fails."""
    pass


class MetadataError(CDRipperError):
    """Base exception for metadata operations."""
    pass


class MetadataNotFoundError(MetadataError):
    """Raised when search query returns no matching album."""
    pass


class MetadataNetworkError(MetadataError):
    """Raised when iTunes API network request fails or times out."""
    pass


class EncodingError(CDRipperError):
    """Raised when audio encoding or tagging fails."""
    pass


class FFmpegNotFoundError(EncodingError):
    """Raised when ffmpeg executable cannot be found in system PATH."""
    pass