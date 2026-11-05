"""Unit tests for App View initialization and GUI components (TC-NFR-01)."""
import sys
import unittest

try:
    import tkinter as tk
    from cdripper.hardware.virtual_drive import VirtualCDDrive
    from cdripper.metadata.mock_provider import MockMetadataProvider
    from cdripper.ui.app_view import CDRipperAppView, set_high_dpi_awareness
    from cdripper.ui.presenter import CDRipperPresenter
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False


class TestAppView(unittest.TestCase):
    def test_high_dpi_initialization_does_not_crash(self):
        # Should execute safely on any platform
        set_high_dpi_awareness()

    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or running in headless CI without display")
    def test_app_view_init(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        drive = VirtualCDDrive()
        meta = MockMetadataProvider()
        presenter = CDRipperPresenter(drive=drive, metadata_provider=meta)
        app = CDRipperAppView(root, presenter)

        self.assertIsNotNone(app.drive_combo)
        self.assertIsNotNone(app.tree)
        root.destroy()


if __name__ == "__main__":
    unittest.main()