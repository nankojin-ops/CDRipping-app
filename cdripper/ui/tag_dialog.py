"""Track Tag Edit Dialog for editing individual track metadata."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from cdripper.domain.models import TrackTagData
from cdripper.domain.validation import (
    parse_and_validate_fractional_tag,
    sanitize_tag_string,
    validate_date_string,
)


class TrackTagEditDialog(tk.Toplevel):
    """
    Modal dialog allowing full editing of metadata tag fields for an individual track.
    Provides previous/next navigation, robust validation, and safe grab release lifecycle.
    (CHALLENGE-004, CHALLENGE-005, AC-001, AC-004, FIND-001)
    """

    def __init__(
        self,
        parent: tk.Misc,
        track_number: int,
        presenter,  # CDRipperPresenter
        on_save_callback: Optional[Callable[[int, TrackTagData], None]] = None,
        on_close_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.presenter = presenter
        self.track_number = track_number
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback

        self.title(f"Edit Track Tags - Track {self.track_number}")
        self.geometry("480x450")
        self.resizable(False, False)

        # Modal lifecycle (CHALLENGE-005, TC-STATE-002, TC-STATE-004, TC-STATE-005)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._safe_close)
        self.bind("<Escape>", lambda _e: self._safe_close())

        self._init_ui()
        self._load_track_data(self.track_number)

        try:
            self.grab_set()
        except Exception:
            pass

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        # Title
        ttk.Label(main_frame, text="Title:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_title = ttk.Entry(main_frame, width=42)
        self.txt_title.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        # Artist
        ttk.Label(main_frame, text="Artist:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_artist = ttk.Entry(main_frame, width=42)
        self.txt_artist.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        # Album Artist (FIND-001)
        ttk.Label(main_frame, text="Album Artist:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_album_artist = ttk.Entry(main_frame, width=42)
        self.txt_album_artist.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        # Album
        ttk.Label(main_frame, text="Album:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_album = ttk.Entry(main_frame, width=42)
        self.txt_album.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        row += 1
        # Track No / Total
        ttk.Label(main_frame, text="Track No:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_track_no = ttk.Entry(main_frame, width=8)
        self.txt_track_no.grid(row=row, column=1, sticky=tk.W, pady=4)

        ttk.Label(main_frame, text="of Total:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(10, 5))
        self.txt_track_total = ttk.Entry(main_frame, width=8)
        self.txt_track_total.grid(row=row, column=3, sticky=tk.W, pady=4)

        row += 1
        # Disc No / Total
        ttk.Label(main_frame, text="Disc No:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_disc_no = ttk.Entry(main_frame, width=8)
        self.txt_disc_no.grid(row=row, column=1, sticky=tk.W, pady=4)

        ttk.Label(main_frame, text="of Total:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(10, 5))
        self.txt_disc_total = ttk.Entry(main_frame, width=8)
        self.txt_disc_total.grid(row=row, column=3, sticky=tk.W, pady=4)

        row += 1
        # Year / Date
        ttk.Label(main_frame, text="Year / Date:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_date = ttk.Entry(main_frame, width=15)
        self.txt_date.grid(row=row, column=1, sticky=tk.W, pady=4)

        row += 1
        # Genre
        ttk.Label(main_frame, text="Genre:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_genre = ttk.Entry(main_frame, width=25)
        self.txt_genre.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=4)

        row += 1
        # Encoder
        ttk.Label(main_frame, text="Encoder:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.txt_encoder = ttk.Entry(main_frame, width=42)
        self.txt_encoder.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=4)

        # Nav & Action Buttons
        btn_frame = ttk.Frame(main_frame, padding=(0, 15, 0, 0))
        btn_frame.grid(row=row + 1, column=0, columnspan=4, sticky=tk.EW)

        self.btn_prev = ttk.Button(btn_frame, text="< Prev Track", command=self._on_prev)
        self.btn_prev.pack(side=tk.LEFT, padx=3)

        self.btn_next = ttk.Button(btn_frame, text="Next Track >", command=self._on_next)
        self.btn_next.pack(side=tk.LEFT, padx=3)

        self.btn_cancel = ttk.Button(btn_frame, text="Cancel", command=self._safe_close)
        self.btn_cancel.pack(side=tk.RIGHT, padx=3)

        self.btn_save = ttk.Button(btn_frame, text="Save", command=self._on_save)
        self.btn_save.pack(side=tk.RIGHT, padx=3)

    def _get_sorted_track_numbers(self) -> list[int]:
        if self.presenter.current_toc and self.presenter.current_toc.tracks:
            return [t.track_number for t in self.presenter.current_toc.tracks]
        all_tags = self.presenter.get_all_track_tags()
        if all_tags:
            return sorted(all_tags.keys())
        return [self.track_number]

    def _update_nav_buttons(self):
        track_nums = self._get_sorted_track_numbers()
        if not track_nums:
            self.btn_prev.config(state=tk.DISABLED)
            self.btn_next.config(state=tk.DISABLED)
            return

        idx = track_nums.index(self.track_number) if self.track_number in track_nums else 0
        self.btn_prev.config(state=tk.NORMAL if idx > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if idx < len(track_nums) - 1 else tk.DISABLED)

    def _load_track_data(self, track_number: int):
        self.track_number = track_number
        self.title(f"Edit Track Tags - Track {self.track_number}")

        tag = self.presenter.get_track_tag(track_number)
        if not tag:
            tag = TrackTagData.create_default(
                track_number=track_number,
                total_tracks=len(self._get_sorted_track_numbers()),
            )

        self._set_entry_text(self.txt_title, tag.title)
        self._set_entry_text(self.txt_artist, tag.artist)
        self._set_entry_text(self.txt_album_artist, tag.album_artist)
        self._set_entry_text(self.txt_album, tag.album)
        self._set_entry_text(self.txt_track_no, str(tag.track_number))
        self._set_entry_text(self.txt_track_total, str(tag.total_tracks) if tag.total_tracks > 0 else "")
        self._set_entry_text(self.txt_disc_no, str(tag.disc_number))
        self._set_entry_text(self.txt_disc_total, str(tag.total_discs) if tag.total_discs > 0 else "")
        self._set_entry_text(self.txt_date, tag.date)
        self._set_entry_text(self.txt_genre, tag.genre)
        self._set_entry_text(self.txt_encoder, tag.encoder)

        self._update_nav_buttons()

    @staticmethod
    def _set_entry_text(entry: ttk.Entry, text: str):
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _validate_and_build_model(self, force_customized: bool = True) -> TrackTagData:
        # Validate track numbers
        trk_no_raw = self.txt_track_no.get().strip()
        trk_tot_raw = self.txt_track_total.get().strip()
        trk_combined = f"{trk_no_raw}/{trk_tot_raw}" if trk_tot_raw else trk_no_raw
        trk_num, trk_total = parse_and_validate_fractional_tag(trk_combined, field_name="track")

        # Validate disc numbers
        disc_no_raw = self.txt_disc_no.get().strip()
        disc_tot_raw = self.txt_disc_total.get().strip()
        disc_combined = f"{disc_no_raw}/{disc_tot_raw}" if disc_tot_raw else disc_no_raw
        disc_num, disc_total = parse_and_validate_fractional_tag(disc_combined, field_name="disc")

        # Validate date
        date_str = validate_date_string(self.txt_date.get())

        # Sanitize strings
        title = sanitize_tag_string(self.txt_title.get())
        if not title:
            title = f"Track {trk_num:02d}"

        artist = sanitize_tag_string(self.txt_artist.get())
        album_artist = sanitize_tag_string(self.txt_album_artist.get())
        album = sanitize_tag_string(self.txt_album.get())
        genre = sanitize_tag_string(self.txt_genre.get())
        encoder = sanitize_tag_string(self.txt_encoder.get()) or "CD Ripping App (iTunes Compatible)"

        orig = self.presenter.get_track_tag(self.track_number)

        # FIND-003: Determine if actually changed from original
        has_changed = (
            orig is None
            or orig.track_number != trk_num
            or orig.total_tracks != trk_total
            or orig.disc_number != disc_num
            or orig.total_discs != disc_total
            or orig.title != title
            or orig.artist != artist
            or orig.album_artist != album_artist
            or orig.album != album
            or orig.date != date_str
            or orig.genre != genre
            or orig.encoder != encoder
        )

        is_customized = True if (force_customized or has_changed) else (orig.is_customized if orig else False)

        return TrackTagData(
            track_number=trk_num,
            total_tracks=trk_total,
            disc_number=disc_num,
            total_discs=disc_total,
            title=title,
            artist=artist,
            album_artist=album_artist,
            album=album,
            date=date_str,
            genre=genre,
            encoder=encoder,
            is_customized=is_customized,
        )

    def _on_save(self):
        try:
            model = self._validate_and_build_model(force_customized=True)
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return

        self.presenter.update_track_tag(self.track_number, model)
        if self.on_save_callback:
            self.on_save_callback(self.track_number, model)

        self._safe_close()

    def _save_if_changed(self) -> None:
        """Helper to validate and save only if user modified any field (FIND-003)."""
        orig = self.presenter.get_track_tag(self.track_number)
        model = self._validate_and_build_model(force_customized=False)
        if model.is_customized or (orig and orig.is_customized):
            self.presenter.update_track_tag(self.track_number, model)
            if self.on_save_callback:
                self.on_save_callback(self.track_number, model)

    def _on_prev(self):
        track_nums = self._get_sorted_track_numbers()
        if self.track_number not in track_nums:
            return

        try:
            self._save_if_changed()
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return

        idx = track_nums.index(self.track_number)
        if idx > 0:
            self._load_track_data(track_nums[idx - 1])

    def _on_next(self):
        track_nums = self._get_sorted_track_numbers()
        if self.track_number not in track_nums:
            return

        try:
            self._save_if_changed()
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return

        idx = track_nums.index(self.track_number)
        if idx < len(track_nums) - 1:
            self._load_track_data(track_nums[idx + 1])

    def _safe_close(self):
        """Safely release modal grab and destroy window (CHALLENGE-005)."""
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
