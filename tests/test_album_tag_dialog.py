"""Unit tests for AlbumTagEditDialog (TASK-003, TC-AC002-*, TC-AC004-*, TC-BND-*, TC-NEG-*, TC-CONC-*)."""
import unittest
from unittest.mock import MagicMock, patch

try:
    import tkinter as tk
    from cdripper.domain.models import AlbumTagData
    from cdripper.ui.album_tag_dialog import AlbumTagEditDialog
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False


class TestAlbumTagDialog(unittest.TestCase):
    @unittest.skipUnless(TK_AVAILABLE, "Tkinter not available or headless CI")
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for Tkinter GUI test.")
            return

        self.initial_data = AlbumTagData(
            disc_number=1,
            total_discs=2,
            album_artist="Test Artist",
            album="Test Album",
            date="2026",
            genre="Rock",
            artwork_data=None,
        )

    def tearDown(self):
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_dialog_field_mapping(self):
        """TC-AC002-01: All fields mapped correctly to entry widgets."""
        dlg = AlbumTagEditDialog(self.root, album_data=self.initial_data)
        self.assertEqual(dlg.txt_album.get(), "Test Album")
        self.assertEqual(dlg.txt_album_artist.get(), "Test Artist")
        self.assertEqual(dlg.txt_disc_no.get(), "1")
        self.assertEqual(dlg.txt_disc_total.get(), "2")
        self.assertEqual(dlg.txt_date.get(), "2026")
        self.assertEqual(dlg.txt_genre.get(), "Rock")
        dlg._safe_close()

    def test_save_valid_data_invokes_callback(self):
        """TC-AC002-03: Saving valid inputs constructs AlbumTagData and invokes callback."""
        mock_callback = MagicMock()
        dlg = AlbumTagEditDialog(self.root, album_data=self.initial_data, on_save_callback=mock_callback)

        dlg.txt_album.delete(0, tk.END)
        dlg.txt_album.insert(0, "New Album")
        dlg.txt_album_artist.delete(0, tk.END)
        dlg.txt_album_artist.insert(0, "New Artist")
        dlg.txt_disc_no.delete(0, tk.END)
        dlg.txt_disc_no.insert(0, "2")

        dlg._on_save()
        mock_callback.assert_called_once()
        saved: AlbumTagData = mock_callback.call_args[0][0]
        self.assertEqual(saved.album, "New Album")
        self.assertEqual(saved.album_artist, "New Artist")
        self.assertEqual(saved.disc_number, 2)
        self.assertEqual(saved.total_discs, 2)

    @patch("tkinter.messagebox.showerror")
    def test_validation_error_on_invalid_disc(self, mock_err):
        """TC-BND-004, TC-NEG-001: Invalid disc numbers show validation error."""
        dlg = AlbumTagEditDialog(self.root, album_data=self.initial_data)
        dlg.txt_disc_no.delete(0, tk.END)
        dlg.txt_disc_no.insert(0, "3")
        dlg.txt_disc_total.delete(0, tk.END)
        dlg.txt_disc_total.insert(0, "2")  # 3/2 is invalid

        dlg._on_save()
        mock_err.assert_called_once()
        self.assertTrue(dlg.winfo_exists())
        dlg._safe_close()

    @patch("tkinter.messagebox.showerror")
    def test_validation_error_on_invalid_date(self, mock_err):
        """TC-NEG-008: Invalid date format triggers validation error."""
        dlg = AlbumTagEditDialog(self.root, album_data=self.initial_data)
        dlg.txt_date.delete(0, tk.END)
        dlg.txt_date.insert(0, "invalid_year")

        dlg._on_save()
        mock_err.assert_called_once()
        self.assertTrue(dlg.winfo_exists())
        dlg._safe_close()

    def test_clear_artwork_resets_data(self):
        """TC-AC004-04: Clear Artwork button removes current artwork."""
        data_with_art = AlbumTagData(
            disc_number=1,
            total_discs=1,
            album="Art Album",
            artwork_data=b"dummy_art",
        )
        dlg = AlbumTagEditDialog(self.root, album_data=data_with_art)
        self.assertEqual(dlg.current_artwork_data, b"dummy_art")

        dlg._on_clear_artwork()
        self.assertIsNone(dlg.current_artwork_data)
        dlg._safe_close()

    def test_safe_close_releases_grab(self):
        """TC-CONC-005: Dialog safe_close releases modal grab."""
        dlg = AlbumTagEditDialog(self.root, album_data=self.initial_data)
        dlg._safe_close()
        self.assertFalse(dlg.winfo_exists())


    def test_on_choose_artwork_rejects_oversized_file_pre_check(self):
        """SEC-001: Rejects oversized file via os.path.getsize without reading full file into memory."""
        dialog = AlbumTagEditDialog(self.root, self.initial_data)
        import unittest.mock
        with unittest.mock.patch('tkinter.filedialog.askopenfilename', return_value='dummy_huge.iso'):
            with unittest.mock.patch('os.path.getsize', return_value=50 * 1024 * 1024):
                with unittest.mock.patch('tkinter.messagebox.showerror') as mock_err:
                    with unittest.mock.patch('builtins.open') as mock_open:
                        dialog._on_choose_artwork()
                        mock_err.assert_called_once()
                        mock_open.assert_not_called()  # Proves file was NOT opened/read into memory!
        dialog._safe_close()

if __name__ == "__main__":
    unittest.main()
