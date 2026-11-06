"""Unit tests for TrackTagEditDialog UI component (TASK-002, TC-META-*, TC-NAV-*, TC-EDIT-*, TC-AC006-*)."""
import unittest
from unittest.mock import MagicMock, patch

try:
    import tkinter as tk
    from cdripper.domain.models import DiscTOC, TrackTagData, TrackTOC
    from cdripper.hardware.virtual_drive import VirtualCDDrive
    from cdripper.metadata.mock_provider import MockMetadataProvider
    from cdripper.ui.presenter import CDRipperPresenter
    from cdripper.ui.tag_dialog import TrackTagEditDialog
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False


class TestTagDialog(unittest.TestCase):
    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or headless CI")
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        self.drive = VirtualCDDrive(track_durations=[2, 2, 2])
        self.meta = MockMetadataProvider()
        self.presenter = CDRipperPresenter(drive=self.drive, metadata_provider=self.meta)

        # Setup mock TOC with 3 tracks
        self.presenter.current_toc = DiscTOC(
            first_track=1,
            last_track=3,
            total_tracks=3,
            total_duration_seconds=6.0,
            tracks=[
                TrackTOC(1, 0, 150, 150, 2.0, True),
                TrackTOC(2, 150, 300, 150, 2.0, True),
                TrackTOC(3, 300, 450, 150, 2.0, True),
            ],
        )
        self.presenter.track_tags = {
            1: TrackTagData.create_default(1, 3, title="Track 01", artist="Artist 1", album_artist="Main Artist"),
            2: TrackTagData.create_default(2, 3, title="Track 02", artist="Artist 2", album_artist="Main Artist"),
            3: TrackTagData.create_default(3, 3, title="Track 03", artist="Artist 3", album_artist="Main Artist"),
        }

    def tearDown(self):
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_dialog_field_mapping_includes_album_artist(self):
        """TC-AC006-01, FIND-001: album_artist is loaded and displayed in dialog."""
        dlg = TrackTagEditDialog(self.root, track_number=2, presenter=self.presenter)
        self.assertEqual(dlg.txt_title.get(), "Track 02")
        self.assertEqual(dlg.txt_artist.get(), "Artist 2")
        self.assertEqual(dlg.txt_album_artist.get(), "Main Artist")
        self.assertEqual(dlg.txt_track_no.get(), "2")
        self.assertEqual(dlg.txt_track_total.get(), "3")
        dlg._safe_close()

    def test_save_preserves_album_artist_on_title_edit(self):
        """TC-AC006-02, FIND-001: Editing only title preserves existing album_artist without loss."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        dlg.txt_title.delete(0, tk.END)
        dlg.txt_title.insert(0, "New Title")

        dlg._on_save()
        saved = self.presenter.get_track_tag(1)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.title, "New Title")
        self.assertEqual(saved.album_artist, "Main Artist")  # Preserved!

    def test_save_updates_edited_album_artist(self):
        """TC-AC006-03: Editing album_artist field updates saved model."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        dlg.txt_album_artist.delete(0, tk.END)
        dlg.txt_album_artist.insert(0, "Updated Band")

        dlg._on_save()
        saved = self.presenter.get_track_tag(1)
        self.assertEqual(saved.album_artist, "Updated Band")

    def test_navigation_prev_disabled_on_first(self):
        """TC-NAV-003: Prev button is disabled on track 1."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        self.assertEqual(str(dlg.btn_prev["state"]), tk.DISABLED)
        self.assertEqual(str(dlg.btn_next["state"]), tk.NORMAL)
        dlg._safe_close()

    def test_navigation_next_disabled_on_last(self):
        """TC-NAV-004: Next button is disabled on track 3 (last)."""
        dlg = TrackTagEditDialog(self.root, track_number=3, presenter=self.presenter)
        self.assertEqual(str(dlg.btn_prev["state"]), tk.NORMAL)
        self.assertEqual(str(dlg.btn_next["state"]), tk.DISABLED)
        dlg._safe_close()

    @patch("tkinter.messagebox.showerror")
    def test_validation_error_keeps_dialog_open(self, mock_err):
        """TC-VAL-001: Invalid input triggers error and dialog stays open."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        dlg.txt_track_no.delete(0, tk.END)
        dlg.txt_track_no.insert(0, "0")  # Invalid track number

        dlg._on_save()
        mock_err.assert_called_once()
        self.assertTrue(dlg.winfo_exists())
        dlg._safe_close()

    def test_save_updates_presenter_and_sets_customized(self):
        """TC-EDIT-001: Saving updates presenter with is_customized=True."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        dlg.txt_title.delete(0, tk.END)
        dlg.txt_title.insert(0, "New Title")
        dlg.txt_artist.delete(0, tk.END)
        dlg.txt_artist.insert(0, "New Artist")

        dlg._on_save()
        saved = self.presenter.get_track_tag(1)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.title, "New Title")
        self.assertEqual(saved.artist, "New Artist")
        self.assertTrue(saved.is_customized)

    def test_save_empty_track_total_preserves_single_number(self):
        """FIND-002: Clearing track total results in total_tracks=0 and single track tag value."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        dlg.txt_track_total.delete(0, tk.END)  # Empty total

        dlg._on_save()
        saved = self.presenter.get_track_tag(1)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.total_tracks, 0)
        self.assertEqual(saved.track_tag_value, "1")

    def test_navigation_without_modification_preserves_uncustomized(self):
        """FIND-003: Navigating with Next/Prev without changes keeps is_customized=False."""
        dlg = TrackTagEditDialog(self.root, track_number=1, presenter=self.presenter)
        self.assertFalse(self.presenter.get_track_tag(1).is_customized)

        dlg._on_next()
        self.assertFalse(self.presenter.get_track_tag(1).is_customized)
        self.assertEqual(dlg.track_number, 2)
        dlg._safe_close()


if __name__ == "__main__":
    unittest.main()
