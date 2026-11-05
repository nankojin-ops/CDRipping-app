"""Hardware layer for CD drive communication and speed optimization."""
from cdripper.hardware.interface import ICDDrive
from cdripper.hardware.virtual_drive import VirtualCDDrive
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer
from cdripper.hardware.spti_drive import WindowsSPTICDDrive

__all__ = [
    "ICDDrive",
    "VirtualCDDrive",
    "DriveSpeedOptimizer",
    "WindowsSPTICDDrive",
]