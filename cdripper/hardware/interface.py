"""Abstract base class interface for CD drives."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from cdripper.domain.models import DiscTOC, DriveInfo


class ICDDrive(ABC):
    """Abstract interface for CD/DVD optical drive hardware operations."""

    @abstractmethod
    def list_drives(self) -> List[DriveInfo]:
        """Detect and return a list of available optical drives."""
        raise NotImplementedError

    @abstractmethod
    def open(self, drive_letter: str) -> bool:
        """Open the optical drive handle."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close the optical drive handle."""
        raise NotImplementedError

    @abstractmethod
    def read_toc(self) -> DiscTOC:
        """Read the disc Table of Contents (TOC)."""
        raise NotImplementedError

    @abstractmethod
    def set_read_speed(self, speed_x: int) -> bool:
        """Set the CD read speed in multiple of 1x (176.4 KB/s)."""
        raise NotImplementedError

    @abstractmethod
    def read_sectors_raw(self, start_lba: int, sector_count: int) -> bytes:
        """Read raw CD-DA audio sectors (2352 bytes per sector)."""
        raise NotImplementedError