"""Drive read speed optimization and adaptive fallback logic."""
from __future__ import annotations

from typing import Optional

from cdripper.domain.models import BusType, DriveInfo


class DriveSpeedOptimizer:
    """Calculates safe and optimal CD read speeds based on drive hardware characteristics."""

    DEFAULT_USB_SAFE_SPEED = 8
    DEFAULT_SATA_SAFE_SPEED = 16
    DEFAULT_UNKNOWN_SAFE_SPEED = 8

    MIN_SPEED_X = 1
    MAX_SPEED_X = 24

    @classmethod
    def calculate_recommended_speed(cls, drive_info: DriveInfo) -> int:
        """
        Calculate safe recommended read speed for CD ripping.
        - USB external drive: Conservative 8x (or max/3) to prevent buffer underrun and mechanical vibration.
        - SATA/ATAPI internal drive: 16x (or max/3) for stability and low acoustic noise.
        - Fallback: If max speed unknown or <= 0, returns default safe speed.
        - FIND-007: Capped so it never exceeds max_read_speed_x when max_read_speed_x > 0.
        """
        bus = drive_info.bus_type
        max_speed = drive_info.max_read_speed_x

        if max_speed is None or max_speed <= 0:
            return cls.get_safe_fallback_speed(bus)

        calculated = max(1, max_speed // 3)

        if bus == BusType.USB:
            speed = min(calculated, 12)
            rec = max(cls.DEFAULT_USB_SAFE_SPEED, min(speed, cls.MAX_SPEED_X))
        elif bus in (BusType.SATA, BusType.ATAPI):
            speed = min(calculated, 24)
            rec = max(cls.DEFAULT_SATA_SAFE_SPEED, min(speed, cls.MAX_SPEED_X))
        elif bus == BusType.VIRTUAL:
            rec = 8
        else:
            rec = max(cls.DEFAULT_UNKNOWN_SAFE_SPEED, min(calculated, 16))

        # FIND-007 (REV-005): Never exceed physical maximum speed of the drive
        if max_speed > 0:
            rec = min(rec, max_speed)

        return rec

    @classmethod
    def get_safe_fallback_speed(cls, bus_type: Optional[BusType]) -> int:
        """Return safe default speed when drive performance details are unavailable."""
        if bus_type == BusType.USB:
            return cls.DEFAULT_USB_SAFE_SPEED
        elif bus_type in (BusType.SATA, BusType.ATAPI):
            return cls.DEFAULT_SATA_SAFE_SPEED
        return cls.DEFAULT_UNKNOWN_SAFE_SPEED

    @classmethod
    def adaptive_speed_down(cls, current_speed_x: int) -> int:
        """
        Step down read speed when read errors or C2 retries occur.
        e.g., 24 -> 16 -> 12 -> 8 -> 4 -> 2 -> 1
        """
        speed_ladder = [24, 16, 12, 8, 4, 2, 1]
        for spd in speed_ladder:
            if spd < current_speed_x:
                return spd
        return cls.MIN_SPEED_X