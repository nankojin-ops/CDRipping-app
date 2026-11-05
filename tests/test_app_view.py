"""Unit tests for App View (TC-NFR-01, FIND-001, FIND-003, FIND-015)."""
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
    from cdripper.domain.models import AlbumMetadata
    from cdripper.hardware.virtual_drive import VirtualCDDrive
    from cdripper.metadata.mock_provider import MockMetadataProvider
    from cdripper.ui.app_view import CDRipperAppView, set_high_dpi_awareness
    from cdripper.ui.presenter import CDRipperPresenter, PresenterEvent
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False


class TestAppView(unittest.TestCase):
    def test_high_dpi_initialization_does_not_crash(self):
        set_high_dpi_awareness()

    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or running in headless CI without display")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.messagebox.showinfo")
    def test_app_view_init_and_error_button_restoration(self, mock_info, mock_err, mock_warn):
        """FIND-001 (REV-001): ERROR受信時にボタンがNORMAL/DISABLEDに復元されること"""
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        drive = VirtualCDDrive()
        meta = MockMetadataProvider()
        presenter = CDRipperPresenter(drive=drive, metadata_provider=meta)
        app = CDRipperAppView(root, presenter)

        # 模擬的にボタンを反転
        app.btn_start_rip.config(state=tk.DISABLED)
        app.btn_cancel.config(state=tk.NORMAL)

        # PresenterEvent.ERROR をシミュレート
        app._handle_presenter_event(PresenterEvent.ERROR, "Simulated Error")
        self.assertEqual(str(app.btn_start_rip["state"]), tk.NORMAL)
        self.assertEqual(str(app.btn_cancel["state"]), tk.DISABLED)
        mock_warn.assert_called_once_with("Notice", "Simulated Error")

        root.destroy()


if __name__ == "__main__":
    unittest.main()
