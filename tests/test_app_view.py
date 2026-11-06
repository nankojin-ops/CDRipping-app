"""Unit tests for App View (AC-001, AC-002, FIND-005, FIND-006, TC-STATE-001)."""
from io import BytesIO
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

try:
    import tkinter as tk
    from cdripper.domain.models import AlbumMetadata, AlbumTagData, DiscTOC, TrackTagData, TrackTOC
    from cdripper.hardware.virtual_drive import VirtualCDDrive
    from cdripper.metadata.mock_provider import MockMetadataProvider
    from cdripper.ui.app_view import CDRipperAppView, set_high_dpi_awareness
    from cdripper.ui.presenter import CDRipperPresenter, PresenterEvent
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False


def _make_dummy_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (1200, 1200), color=(100, 150, 200))
    bio = BytesIO()
    img.save(bio, format="JPEG")
    return bio.getvalue()


class TestAppView(unittest.TestCase):
    def test_high_dpi_initialization_does_not_crash(self):
        set_high_dpi_awareness()

    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or running in headless CI without display")
    def test_jpeg_artwork_rendering_no_tcl_error(self):
        """TC-AC001-01, AC-001: Renders high-res JPEG artwork on canvas without TclError."""
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        drive = VirtualCDDrive()
        meta = MockMetadataProvider()
        presenter = CDRipperPresenter(drive=drive, metadata_provider=meta)
        app = CDRipperAppView(root, presenter)

        jpeg_data = _make_dummy_jpeg_bytes()
        album = AlbumMetadata(
            collection_id=1,
            album_name="JPEG Album",
            artist_name="Artist",
            release_year="2026",
            genre="Pop",
            total_tracks=1,
            artwork_data=jpeg_data,
        )

        # Dispatch METADATA_LOADED with JPEG data
        app._handle_presenter_event(PresenterEvent.METADATA_LOADED, album)
        self.assertIsNotNone(app._artwork_photo)
        root.destroy()

    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or running in headless CI without display")
    def test_album_tags_updated_syncs_ui_entries(self):
        """TC-AC003-05, FIND-006: ALBUM_TAGS_UPDATED immediately synchronizes main UI text entries."""
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        drive = VirtualCDDrive()
        meta = MockMetadataProvider()
        presenter = CDRipperPresenter(drive=drive, metadata_provider=meta)
        app = CDRipperAppView(root, presenter)

        album_data = AlbumTagData(
            album="Synchronized Album",
            album_artist="Synchronized Artist",
            artwork_data=None,
        )

        app._handle_presenter_event(PresenterEvent.ALBUM_TAGS_UPDATED, album_data)
        self.assertEqual(app.txt_album.get(), "Synchronized Album")
        self.assertEqual(app.txt_artist.get(), "Synchronized Artist")
        root.destroy()

    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or running in headless CI without display")
    def test_set_ripping_ui_state_disables_album_edit_button(self):
        """TC-CONC-001, FIND-005: Disables Edit Album Tags button during ripping."""
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        drive = VirtualCDDrive()
        meta = MockMetadataProvider()
        presenter = CDRipperPresenter(drive=drive, metadata_provider=meta)
        app = CDRipperAppView(root, presenter)

        app._set_ripping_ui_state(True)
        self.assertEqual(str(app.btn_edit_album["state"]), tk.DISABLED)

        app._set_ripping_ui_state(False)
        self.assertEqual(str(app.btn_edit_album["state"]), tk.NORMAL)
        root.destroy()


if __name__ == "__main__":
    unittest.main()
