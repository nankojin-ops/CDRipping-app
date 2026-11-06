"""Album Tag Edit Dialog for editing album-wide metadata and artwork."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from cdripper.domain.models import AlbumTagData
from cdripper.domain.validation import (
    parse_and_validate_fractional_tag,
    sanitize_tag_string,
    validate_date_string,
)
from cdripper.ui.artwork_helper import (
    MAX_ARTWORK_SIZE_BYTES,
    create_photo_image,
    normalize_artwork,
)


class AlbumTagEditDialog(tk.Toplevel):
    """
    Modal dialog allowing full editing of album-level metadata and cover artwork.
    Safely normalizes chosen images, manages Tkinter modal grab, and prevents double-open.
    (AC-002, AC-004, FIND-002, FIND-005, FIND-007)
    """

    def __init__(
        self,
        parent: tk.Misc,
        album_data: AlbumTagData,
        on_save_callback: Optional[Callable[[AlbumTagData], None]] = None,
        on_close_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.initial_data = album_data
        self.current_artwork_data: Optional[bytes] = album_data.artwork_data
        self._preview_photo: Optional[tk.PhotoImage] = None  # GC protection
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback

        self.title("Edit Album Tags & Artwork")
        self.geometry("540x440")
        self.resizable(False, False)

        # Modal lifecycle
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._safe_close)
        self.bind("<Escape>", lambda _e: self._safe_close())

        self._init_ui()
        self._load_data(album_data)

        try:
            self.grab_set()
        except Exception:
            pass

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left side: Metadata inputs
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        row = 0
        ttk.Label(left_frame, text="Album Title:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_album = ttk.Entry(left_frame, width=28)
        self.txt_album.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        ttk.Label(left_frame, text="Album Artist:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_album_artist = ttk.Entry(left_frame, width=28)
        self.txt_album_artist.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        ttk.Label(left_frame, text="Disc No:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_disc_no = ttk.Entry(left_frame, width=6)
        self.txt_disc_no.grid(row=row, column=1, sticky=tk.W, pady=4)

        ttk.Label(left_frame, text="of Total:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(8, 4))
        self.txt_disc_total = ttk.Entry(left_frame, width=6)
        self.txt_disc_total.grid(row=row, column=3, sticky=tk.W, pady=4)

        row += 1
        ttk.Label(left_frame, text="Year / Date:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_date = ttk.Entry(left_frame, width=12)
        self.txt_date.grid(row=row, column=1, sticky=tk.W, pady=4)

        row += 1
        ttk.Label(left_frame, text="Genre:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_genre = ttk.Entry(left_frame, width=20)
        self.txt_genre.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=4)

        # Right side: Artwork preview and controls
        right_frame = ttk.LabelFrame(content_frame, text=" Artwork ", padding=8)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        self.art_canvas = tk.Canvas(right_frame, width=120, height=120, bg="#e0e0e0", relief="sunken", borderwidth=1)
        self.art_canvas.pack(pady=(0, 8))

        self.btn_choose_art = ttk.Button(right_frame, text="Choose Artwork...", command=self._on_choose_artwork)
        self.btn_choose_art.pack(fill=tk.X, pady=2)

        self.btn_clear_art = ttk.Button(right_frame, text="Clear Artwork", command=self._on_clear_artwork)
        self.btn_clear_art.pack(fill=tk.X, pady=2)

        # Bottom: OK / Cancel
        btn_frame = ttk.Frame(main_frame, padding=(0, 15, 0, 0))
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_cancel = ttk.Button(btn_frame, text="Cancel", command=self._safe_close)
        self.btn_cancel.pack(side=tk.RIGHT, padx=3)

        self.btn_save = ttk.Button(btn_frame, text="Save Album Tags", command=self._on_save)
        self.btn_save.pack(side=tk.RIGHT, padx=3)

    def _load_data(self, data: AlbumTagData):
        self._set_entry_text(self.txt_album, data.album)
        self._set_entry_text(self.txt_album_artist, data.album_artist)
        self._set_entry_text(self.txt_disc_no, str(data.disc_number))
        self._set_entry_text(self.txt_disc_total, str(data.total_discs) if data.total_discs > 0 else "")
        self._set_entry_text(self.txt_date, data.date)
        self._set_entry_text(self.txt_genre, data.genre)

        self._update_artwork_preview()

    def _update_artwork_preview(self):
        if self.current_artwork_data:
            photo = create_photo_image(self.current_artwork_data, max_size=(120, 120))
            if photo:
                self._preview_photo = photo
                self.art_canvas.delete("all")
                self.art_canvas.create_image(60, 60, image=self._preview_photo)
                return

        self._draw_no_artwork()

    def _draw_no_artwork(self):
        self._preview_photo = None
        self.art_canvas.delete("all")
        self.art_canvas.create_text(60, 60, text="No Artwork\n(Click Choose)", fill="#888888", justify=tk.CENTER)

    def _on_choose_artwork(self):
        filetypes = [
            ("Image files", "*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.tiff"),
            ("JPEG files", "*.jpg;*.jpeg"),
            ("PNG files", "*.png"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(parent=self, title="Select Album Artwork", filetypes=filetypes)
        if not path:
            return

        import os
        try:
            # SEC-001: Pre-check file size before reading into memory to prevent DoS / MemoryError
            file_size = os.path.getsize(path)
            if file_size > MAX_ARTWORK_SIZE_BYTES:
                messagebox.showerror(
                    "Image Too Large",
                    f"Selected image is too large ({file_size / (1024 * 1024):.1f} MB). Maximum allowed size is 10 MB.",
                    parent=self,
                )
                return

            with open(path, "rb") as f:
                data = f.read(MAX_ARTWORK_SIZE_BYTES + 1)

            if len(data) > MAX_ARTWORK_SIZE_BYTES:
                messagebox.showerror(
                    "Image Too Large",
                    "Selected image is too large. Maximum allowed size is 10 MB.",
                    parent=self,
                )
                return

            normalized = normalize_artwork(data, max_dimension=1400)
            if normalized is None:
                messagebox.showerror(
                    "Invalid Image",
                    "The selected file could not be decoded as a valid supported image.",
                    parent=self,
                )
                return

            self.current_artwork_data = normalized
            self._update_artwork_preview()
        except Exception as e:
            messagebox.showerror("Error Reading File", f"Failed to load image: {e}", parent=self)

    def _on_clear_artwork(self):
        self.current_artwork_data = None
        self._update_artwork_preview()

    @staticmethod
    def _set_entry_text(entry: ttk.Entry, text: str):
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _validate_and_build_model(self) -> AlbumTagData:
        # Validate disc numbers
        disc_no_raw = self.txt_disc_no.get().strip()
        disc_tot_raw = self.txt_disc_total.get().strip()
        disc_combined = f"{disc_no_raw}/{disc_tot_raw}" if disc_tot_raw else disc_no_raw
        disc_num, disc_total = parse_and_validate_fractional_tag(disc_combined, field_name="disc")

        # Validate date
        date_str = validate_date_string(self.txt_date.get())

        # Sanitize strings
        album = sanitize_tag_string(self.txt_album.get(), max_length=256)
        album_artist = sanitize_tag_string(self.txt_album_artist.get(), max_length=256)
        genre = sanitize_tag_string(self.txt_genre.get(), max_length=256)

        return AlbumTagData(
            disc_number=disc_num,
            total_discs=disc_total,
            album_artist=album_artist,
            album=album,
            date=date_str,
            genre=genre,
            artwork_data=self.current_artwork_data,
        )

    def _on_save(self):
        try:
            model = self._validate_and_build_model()
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return

        if self.on_save_callback:
            self.on_save_callback(model)

        self._safe_close()

    def _safe_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception:
                pass

        self.destroy()
