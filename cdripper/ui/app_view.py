"""Tkinter Desktop UI implementation for CD Ripping Application."""
from __future__ import annotations

import base64
import ctypes
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

from cdripper.domain.models import (
    AlbumMetadata,
    AlbumTagData,
    BusType,
    DiscTOC,
    DriveInfo,
    EncodeFormat,
    RipConfig,
    RipProgress,
    TrackTagData,
)
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.ui.album_tag_dialog import AlbumTagEditDialog
from cdripper.ui.artwork_helper import create_photo_image
from cdripper.ui.presenter import CDRipperPresenter, PresenterEvent
from cdripper.ui.tag_dialog import TrackTagEditDialog


def set_high_dpi_awareness():
    """Enable Windows Per-Monitor High DPI awareness."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


class CDRipperAppView:
    """Main Desktop GUI Window for CD Ripping."""

    def __init__(self, root: tk.Tk, presenter: CDRipperPresenter):
        self.root = root
        self.presenter = presenter
        self.root.title("CD Ripping App - iTunes High Quality Ripping")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        self._artwork_photo: Optional[tk.PhotoImage] = None  # GC prevention (FIND-003)
        self._tag_dialog_instance: Optional[TrackTagEditDialog] = None  # Singleton dialog (CHALLENGE-005)
        self._album_dialog_instance: Optional[AlbumTagEditDialog] = None  # FIND-005

        self._init_ui()
        self._start_queue_polling()

    def _init_ui(self):
        top_frame = ttk.LabelFrame(self.root, text=" Drive & Hardware Settings ", padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(top_frame, text="Drive:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.drive_var = tk.StringVar()
        self.drive_combo = ttk.Combobox(top_frame, textvariable=self.drive_var, state="readonly", width=35)
        self.drive_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        self.drive_combo.bind("<<ComboboxSelected>>", self._on_drive_selected)

        self.btn_refresh_drive = ttk.Button(top_frame, text="Refresh", command=self.presenter.scan_drives)
        self.btn_refresh_drive.grid(row=0, column=2, padx=5, pady=2)

        self.btn_virtual_drive = ttk.Button(top_frame, text="Virtual CD Mode", command=self._on_toggle_virtual)
        self.btn_virtual_drive.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(top_frame, text="Read Speed:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.speed_var = tk.StringVar(value="Auto (Optimized)")
        self.speed_combo = ttk.Combobox(
            top_frame,
            textvariable=self.speed_var,
            state="readonly",
            values=["Auto (Optimized)", "4x", "8x", "12x", "16x", "24x", "Max"],
            width=18,
        )
        self.speed_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        self.lbl_speed_info = ttk.Label(top_frame, text="Recommended: 8x (External USB Safe)", foreground="blue")
        self.lbl_speed_info.grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=5, pady=2)

        meta_frame = ttk.LabelFrame(self.root, text=" iTunes Album & Track Metadata ", padding=10)
        meta_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(meta_frame, text="Album:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.txt_album = ttk.Entry(meta_frame, width=30)
        self.txt_album.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        self.txt_album.bind("<FocusOut>", self._on_album_artist_focus_out)

        ttk.Label(meta_frame, text="Artist:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.txt_artist = ttk.Entry(meta_frame, width=25)
        self.txt_artist.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        self.txt_artist.bind("<FocusOut>", self._on_album_artist_focus_out)

        self.btn_itunes_search = ttk.Button(meta_frame, text="Search iTunes...", command=self._open_search_dialog)
        self.btn_itunes_search.grid(row=0, column=4, padx=10, pady=2)

        mid_frame = ttk.Frame(self.root, padding=10)
        mid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tree_frame = ttk.Frame(mid_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("track", "title", "artist", "duration", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        self.tree.heading("track", text="#")
        self.tree.heading("title", text="Track Title")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("duration", text="Time")
        self.tree.heading("status", text="Status")

        self.tree.column("track", width=40, anchor=tk.CENTER)
        self.tree.column("title", width=260, anchor=tk.W)
        self.tree.column("artist", width=180, anchor=tk.W)
        self.tree.column("duration", width=70, anchor=tk.CENTER)
        self.tree.column("status", width=90, anchor=tk.W)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        art_frame = ttk.LabelFrame(mid_frame, text=" Artwork ", padding=5)
        art_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.art_canvas = tk.Canvas(art_frame, width=150, height=150, bg="#e0e0e0")
        self.art_canvas.pack(pady=5)
        self.art_canvas.bind("<Button-1>", lambda _e: self._open_album_tag_dialog())
        try:
            self.art_canvas.config(cursor="hand2")
        except Exception:
            pass
        self._draw_no_artwork()

        enc_frame = ttk.Frame(self.root, padding=10)
        enc_frame.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(enc_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        self.format_var = tk.StringVar(value=EncodeFormat.AAC_256K.value)
        self.format_combo = ttk.Combobox(
            enc_frame,
            textvariable=self.format_var,
            state="readonly",
            values=[f.value for f in EncodeFormat],
            width=22,
        )
        self.format_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(enc_frame, text="Output Folder:").pack(side=tk.LEFT, padx=(15, 5))
        default_music = os.path.join(os.path.expanduser("~"), "Music", "CDRipOutput")
        self.txt_outdir = ttk.Entry(enc_frame, width=35)
        self.txt_outdir.insert(0, default_music)
        self.txt_outdir.pack(side=tk.LEFT, padx=5)

        ctrl_frame = ttk.Frame(self.root, padding=10)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_edit_album = ttk.Button(ctrl_frame, text="Edit Album Tags...", command=self._open_album_tag_dialog)
        self.btn_edit_album.pack(side=tk.LEFT, padx=5)

        self.btn_edit_tags = ttk.Button(ctrl_frame, text="Edit Track Tags...", command=self._on_edit_tags_clicked)
        self.btn_edit_tags.pack(side=tk.LEFT, padx=5)

        self.btn_start_rip = ttk.Button(ctrl_frame, text="Start Ripping", command=self._on_start_rip)
        self.btn_start_rip.pack(side=tk.LEFT, padx=5)

        self.btn_cancel = ttk.Button(ctrl_frame, text="Cancel", command=self.presenter.cancel_ripping, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(ctrl_frame, text="Ready", font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        prog_frame = ttk.Frame(self.root, padding=10)
        prog_frame.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(prog_frame, text="Track Progress:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.prog_track = ttk.Progressbar(prog_frame, orient=tk.HORIZONTAL, mode="determinate")
        self.prog_track.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(prog_frame, text="Total Progress:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.prog_total = ttk.Progressbar(prog_frame, orient=tk.HORIZONTAL, mode="determinate")
        self.prog_total.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)

        prog_frame.columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(self.root, text=" Log Console ", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.txt_log = tk.Text(log_frame, height=5, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 8))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        self.presenter.scan_drives()

    def _draw_no_artwork(self):
        self.art_canvas.delete("all")
        self.art_canvas.create_text(75, 75, text="No Artwork\n(Click to Edit)", fill="#888888", justify=tk.CENTER)

    def _update_artwork_canvas(self, artwork_data: Optional[bytes]):
        """Render artwork image onto canvas with Pillow thumbnail scaling (AC-001)."""
        if artwork_data:
            photo = create_photo_image(artwork_data, max_size=(150, 150))
            if photo:
                self._artwork_photo = photo
                self.art_canvas.delete("all")
                self.art_canvas.create_image(75, 75, image=self._artwork_photo)
                return
        self._draw_no_artwork()

    def _start_queue_polling(self):
        def poll():
            try:
                while True:
                    event, payload = self.presenter.event_queue.get_nowait()
                    self._handle_presenter_event(event, payload)
            except Exception:
                pass
            finally:
                self.root.after(50, poll)

        self.root.after(50, poll)

    def _set_ripping_ui_state(self, is_ripping: bool):
        """Enable or disable all UI controls during ripping (CHALLENGE-002, TC-STATE-001, 006, FIND-005)."""
        state = tk.DISABLED if is_ripping else tk.NORMAL
        combo_state = "disabled" if is_ripping else "readonly"

        self.drive_combo.config(state=combo_state)
        self.btn_refresh_drive.config(state=state)
        self.btn_virtual_drive.config(state=state)
        self.speed_combo.config(state=combo_state)
        self.txt_album.config(state=state)
        self.txt_artist.config(state=state)
        self.btn_itunes_search.config(state=state)
        self.format_combo.config(state=combo_state)
        self.txt_outdir.config(state=state)
        self.btn_edit_album.config(state=state)
        self.btn_edit_tags.config(state=state)
        self.btn_start_rip.config(state=tk.DISABLED if is_ripping else tk.NORMAL)
        self.btn_cancel.config(state=tk.NORMAL if is_ripping else tk.DISABLED)

    def _handle_presenter_event(self, event: str, payload):
        if event == PresenterEvent.DRIVES_LOADED:
            drives: List[DriveInfo] = payload
            combo_values = [f"{d.drive_letter} - {d.display_name}" for d in drives]
            self.drive_combo["values"] = combo_values
            if combo_values:
                self.drive_combo.current(0)
                self._on_drive_selected(None)
            else:
                self.drive_var.set("No optical drive found")

        elif event == PresenterEvent.TOC_LOADED:
            toc: DiscTOC = payload
            self._display_toc(toc)

        elif event == PresenterEvent.METADATA_LOADED:
            album: AlbumMetadata = payload
            self.txt_album.delete(0, tk.END)
            self.txt_album.insert(0, album.album_name)
            self.txt_artist.delete(0, tk.END)
            self.txt_artist.insert(0, album.artist_name)
            self._update_tracks_with_metadata(album)
            self._update_artwork_canvas(album.artwork_data)

        elif event == PresenterEvent.ALBUM_TAGS_UPDATED:
            album_data: AlbumTagData = payload
            self.txt_album.delete(0, tk.END)
            self.txt_album.insert(0, album_data.album)
            self.txt_artist.delete(0, tk.END)
            self.txt_artist.insert(0, album_data.album_artist or self.txt_artist.get())
            self._update_artwork_canvas(album_data.artwork_data)

        elif event == PresenterEvent.TRACK_TAG_UPDATED:
            track_num, tag_data = payload
            self._update_tree_row_with_tag(track_num, tag_data)

        elif event == PresenterEvent.PROGRESS_UPDATE:
            prog: RipProgress = payload
            self.prog_track["value"] = prog.track_progress_percent
            self.prog_total["value"] = prog.overall_progress_percent
            self.lbl_status.config(text=f"{prog.status_text} (Speed: {prog.current_speed_x:.1f}x)")

            if prog.is_finished:
                self._set_ripping_ui_state(False)
                if prog.error_message:
                    messagebox.showerror("Ripping Error", prog.error_message)
                else:
                    messagebox.showinfo("Completed", "CD ripping completed successfully!")

        elif event == PresenterEvent.LOG:
            self._append_log(str(payload))

        elif event == PresenterEvent.ERROR:
            messagebox.showwarning("Notice", str(payload))
            self._set_ripping_ui_state(False)

    def _display_toc(self, toc: DiscTOC):
        self.tree.delete(*self.tree.get_children())
        for t in toc.tracks:
            dur_min = int(t.duration_seconds // 60)
            dur_sec = int(t.duration_seconds % 60)
            dur_str = f"{dur_min:02d}:{dur_sec:02d}"
            tag = self.presenter.get_track_tag(t.track_number)
            title = tag.title if tag else f"Track {t.track_number:02d}"
            artist = tag.artist if tag else "Unknown Artist"
            self.tree.insert(
                "",
                tk.END,
                values=(t.track_number, title, artist, dur_str, "Ready"),
            )

    def _update_tracks_with_metadata(self, album: AlbumMetadata):
        for item_id in self.tree.get_children():
            vals = list(self.tree.item(item_id, "values"))
            track_num = int(vals[0])
            tag = self.presenter.get_track_tag(track_num)
            if tag:
                vals[1] = tag.title
                vals[2] = tag.artist
                self.tree.item(item_id, values=vals)

    def _on_drive_selected(self, _event):
        sel_text = self.drive_var.get()
        if sel_text and " - " in sel_text:
            letter = sel_text.split(" - ")[0].strip()
            self.presenter.select_drive(letter)
            rec_speed = DriveSpeedOptimizer.RECOMMENDED_SAFE_SPEED_X
            self.lbl_speed_info.config(text=f"Recommended: {rec_speed}x (External USB Safe)")

    def _on_toggle_virtual(self):
        self.presenter.switch_to_virtual_drive(has_media=True)
        self.lbl_speed_info.config(text="Mode: Virtual CD (High Speed In-Memory Testing)")

    def _on_tree_double_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        track_number = int(vals[0])
        self._open_tag_edit_dialog(track_number)

    def _on_edit_tags_clicked(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Notice", "Please select a track from the list first.")
            return
        vals = self.tree.item(sel[0], "values")
        track_number = int(vals[0])
        self._open_tag_edit_dialog(track_number)

    def _open_album_tag_dialog(self):
        """Open Album Tag Edit Dialog with mutual exclusion and rip lock (AC-002, FIND-005)."""
        if self.presenter.is_ripping:
            return

        # Mutual exclusion: if track dialog is open, lift it instead
        if self._tag_dialog_instance and self._tag_dialog_instance.winfo_exists():
            self._tag_dialog_instance.lift()
            self._tag_dialog_instance.focus_force()
            return

        # Single instance guard for album dialog
        if self._album_dialog_instance and self._album_dialog_instance.winfo_exists():
            self._album_dialog_instance.lift()
            self._album_dialog_instance.focus_force()
            return

        # Synthesize initial AlbumTagData
        curr_album = self.presenter.current_album
        first_tag = next(iter(self.presenter.track_tags.values()), None)

        disc_no = self.presenter.selected_disc
        total_discs = curr_album.total_discs if curr_album else (first_tag.total_discs if first_tag else 1)
        album_title = curr_album.album_name if curr_album else (first_tag.album if first_tag else self.txt_album.get())
        album_artist = curr_album.album_artist if (curr_album and curr_album.album_artist) else (
            first_tag.album_artist if (first_tag and first_tag.album_artist) else (
                curr_album.artist_name if curr_album else self.txt_artist.get()
            )
        )
        date_val = curr_album.release_year if curr_album else (first_tag.date if first_tag else "")
        genre_val = curr_album.genre if curr_album else (first_tag.genre if first_tag else "")
        art_data = curr_album.artwork_data if curr_album else None

        initial_data = AlbumTagData(
            disc_number=disc_no,
            total_discs=total_discs,
            album_artist=album_artist,
            album=album_title,
            date=date_val,
            genre=genre_val,
            artwork_data=art_data,
        )

        def on_close():
            self._album_dialog_instance = None

        self._album_dialog_instance = AlbumTagEditDialog(
            parent=self.root,
            album_data=initial_data,
            on_save_callback=self.presenter.update_album_tags,
            on_close_callback=on_close,
        )

    def _open_tag_edit_dialog(self, track_number: int):
        if self.presenter.is_ripping:
            return

        # Mutual exclusion: if album dialog is open, lift it instead
        if self._album_dialog_instance and self._album_dialog_instance.winfo_exists():
            self._album_dialog_instance.lift()
            self._album_dialog_instance.focus_force()
            return

        if self._tag_dialog_instance and self._tag_dialog_instance.winfo_exists():
            self._tag_dialog_instance.lift()
            self._tag_dialog_instance.focus_force()
            return

        def on_close():
            self._tag_dialog_instance = None

        self._tag_dialog_instance = TrackTagEditDialog(
            parent=self.root,
            track_number=track_number,
            presenter=self.presenter,
            on_save_callback=self._on_track_tag_saved,
            on_close_callback=on_close,
        )

    def _on_track_tag_saved(self, track_number: int, tag_data: TrackTagData):
        self._update_tree_row_with_tag(track_number, tag_data)

    def _update_tree_row_with_tag(self, track_number: int, tag_data: TrackTagData):
        for item_id in self.tree.get_children():
            vals = list(self.tree.item(item_id, "values"))
            if int(vals[0]) == track_number:
                vals[1] = tag_data.title
                vals[2] = tag_data.artist
                self.tree.item(item_id, values=vals)
                break

    def _on_album_artist_focus_out(self, _event):
        album = self.txt_album.get()
        artist = self.txt_artist.get()
        self.presenter.sync_album_artist_to_uncustomized(album, artist)

    def _open_search_dialog(self):
        query = self.txt_album.get() or self.txt_artist.get() or "The Beatles"
        dlg = tk.Toplevel(self.root)
        dlg.title("Search iTunes CD Metadata")
        dlg.geometry("500x350")
        dlg.transient(self.root)

        top = ttk.Frame(dlg, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Album/Artist:").pack(side=tk.LEFT, padx=5)
        txt_q = ttk.Entry(top, width=30)
        txt_q.insert(0, query)
        txt_q.pack(side=tk.LEFT, padx=5)

        lbl_status = ttk.Label(dlg, text="", foreground="gray")
        lbl_status.pack(anchor=tk.W, padx=10)

        lst = tk.Listbox(dlg)
        lst.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        albums_cache: List[AlbumMetadata] = []

        def do_search():
            q_text = txt_q.get()
            btn_search.config(state=tk.DISABLED)
            lbl_status.config(text="Searching iTunes...")
            lst.delete(0, tk.END)
            albums_cache.clear()

            def worker():
                try:
                    results = self.presenter.metadata_provider.search_albums(q_text)
                    err_msg = None
                except Exception as e:
                    results = []
                    err_msg = str(e)

                def update_ui():
                    btn_search.config(state=tk.NORMAL)
                    if err_msg:
                        lbl_status.config(text=f"Error: {err_msg}")
                    else:
                        lbl_status.config(text=f"Found {len(results)} album(s).")
                        for a in results:
                            albums_cache.append(a)
                            lst.insert(tk.END, f"{a.album_name} - {a.artist_name} ({a.release_year}, {a.total_tracks} tracks)")

                dlg.after(0, update_ui)

            threading.Thread(target=worker, daemon=True).start()

        btn_search = ttk.Button(top, text="Search", command=do_search)
        btn_search.pack(side=tk.LEFT, padx=5)

        def on_select():
            sel = lst.curselection()
            if not sel:
                return
            idx = sel[0]
            chosen = albums_cache[idx]

            overwrite = True
            if self.presenter.has_customized_tracks():
                overwrite = messagebox.askyesno(
                    "Overwrite Confirmation",
                    "Some tracks have custom metadata edits. Overwrite all customized tracks with iTunes metadata?",
                    parent=dlg,
                )

            self.presenter.apply_album_metadata(chosen.collection_id, overwrite_customized=overwrite)
            dlg.destroy()

        btn_apply = ttk.Button(dlg, text="Apply Selected Album", command=on_select)
        btn_apply.pack(pady=5)

    def _on_start_rip(self):
        if not self.presenter.current_toc:
            messagebox.showwarning("Notice", "No disc inserted or TOC not loaded.")
            return

        outdir = self.txt_outdir.get().strip()
        if not outdir:
            messagebox.showwarning("Notice", "Please specify an output folder.")
            return

        fmt_str = self.format_var.get()
        chosen_fmt = EncodeFormat.AAC_256K
        for f in EncodeFormat:
            if f.value == fmt_str:
                chosen_fmt = f
                break

        speed_str = self.speed_var.get()
        speed_x = 8
        if "4x" in speed_str:
            speed_x = 4
        elif "8x" in speed_str:
            speed_x = 8
        elif "12x" in speed_str:
            speed_x = 12
        elif "16x" in speed_str:
            speed_x = 16
        elif "24x" in speed_str:
            speed_x = 24
        elif "Max" in speed_str:
            speed_x = 0

        config = RipConfig(
            output_dir=outdir,
            format=chosen_fmt,
            selected_speed_x=speed_x,
            speed_mode_auto=("Auto" in speed_str),
        )

        self._set_ripping_ui_state(True)
        self.presenter.start_ripping(config)

    def _append_log(self, text: str):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)
