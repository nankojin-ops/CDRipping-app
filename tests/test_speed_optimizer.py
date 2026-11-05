"""Unit tests for DriveSpeedOptimizer (TC-SPD-01, TC-SPD-02, TC-SPD-03, TC-SPD-05)."""
import unittest

from cdripper.domain.models import BusType, DriveInfo
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer


class TestSpeedOptimizer(unittest.TestCase):
    def test_sata_internal_48x(self):
        info = DriveInfo("D:", "SATA Drive", BusType.SATA, True, 48, 0)
        rec = DriveSpeedOptimizer.calculate_recommended_speed(info)
        self.assertEqual(rec, 16)  # 48 // 3 = 16

    def test_usb_external_24x(self):
        info = DriveInfo("E:", "USB External", BusType.USB, True, 24, 0)
        rec = DriveSpeedOptimizer.calculate_recommended_speed(info)
        self.assertEqual(rec, 8)  # 24 // 3 = 8

    def test_unknown_or_missing_speed(self):
        info = DriveInfo("F:", "Unknown", BusType.UNKNOWN, True, 0, 0)
        rec = DriveSpeedOptimizer.calculate_recommended_speed(info)
        self.assertEqual(rec, 8)

    def test_adaptive_speed_down(self):
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(24), 16)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(16), 12)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(12), 8)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(8), 4)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(4), 2)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(2), 1)
        self.assertEqual(DriveSpeedOptimizer.adaptive_speed_down(1), 1)


if __name__ == "__main__":
    unittest.main()