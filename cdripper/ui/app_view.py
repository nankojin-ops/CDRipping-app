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
    BusType,
    DiscTOC,
    DriveInfo,
    EncodeFormat,
    RipConfig,
    RipProgress,
)
from cdripper.hardware.speed_optimizer import DriveSpeedOptimizer
from cdripper.metadata.itunes_client import ITunesApiClient
from cdripper.ui.presenter import CDRipperPresenter, PresenterEvent


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

        ttk.Label(meta_frame, text="Artist:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.txt_artist = ttk.Entry(meta_frame, width=25)
        self.txt_artist.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

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

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        art_frame = ttk.LabelFrame(mid_frame, text=" Artwork ", padding=5)
        art_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.art_canvas = tk.Canvas(art_frame, width=150, height=150, bg="#e0e0e0")
        self.art_canvas.pack(pady=5)
        self._draw_no_artwork()

        enc_frame = ttk.Frame(self.root, padding=10)
        enc_frame.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(enc_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        self.format_var = tk.StringVar(value=EncodeFormat.AAC_256K.value)
        format_combo = ttk.Combobox(
            enc_frame,
            textvariable=self.format_var,
            state="readonly",
            values=[f.value for f in EncodeFormat],
            width=22,
        )
        format_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(enc_frame, text="Output Folder:").pack(side=tk.LEFT, padx=(15, 5))
        default_music = os.path.join(os.path.expanduser("~"), "Music", "CDRipOutput")
        self.txt_outdir = ttk.Entry(enc_frame, width=35)
        self.txt_outdir.insert(0, default_music)
        self.txt_outdir.pack(side=tk.LEFT, padx=5)

        ctrl_frame = ttk.Frame(self.root, padding=10)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=5)

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
        self.art_canvas.create_text(75, 75, text="No Artwork\n(1200x1200bb)", fill="#888888", justify=tk.CENTER)

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

            # FIND-003 (REV-003): Display artwork preview safely
            if album.artwork_data:
                try:
                    b64 = base64.b64encode(album.artwork_data).decode("ascii")
                    self._artwork_photo = tk.PhotoImage(data=b64)
                    self.art_canvas.delete("all")
                    self.art_canvas.create_image(75, 75, image=self._artwork_photo)
                except Exception:
                    self._draw_no_artwork()
            else:
                self._draw_no_artwork()

        elif event == PresenterEvent.PROGRESS_UPDATE:
            prog: RipProgress = payload
            self.prog_track["value"] = prog.track_progress_percent
            self.prog_total["value"] = prog.overall_progress_percent
            self.lbl_status.config(text=f"{prog.status_text} (Speed: {prog.current_speed_x:.1f}x)")

            if prog.is_finished:
                self.btn_start_rip.config(state=tk.NORMAL)
                self.btn_cancel.config(state=tk.DISABLED)
                if prog.error_message:
                    messagebox.showerror("Ripping Error", prog.error_message)
                else:
                    messagebox.showinfo("Completed", "CD ripping completed successfully!")

        elif event == PresenterEvent.LOG:
            self._append_log(str(payload))

        elif event == PresenterEvent.ERROR:
            # FIND-001 (REV-001): Restore button states on error
            self.btn_start_rip.config(state=tk.NORMAL)
            self.btn_cancel.config(state=tk.DISABLED)
            self._append_log(f"ERROR: {payload}")
            messagebox.showwarning("Notice", str(payload))

    def _on_drive_selected(self, _event):
        val = self.drive_var.get()
        if not val or " - " not in val:
            return
        letter = val.split(" - ")[0]
        self.presenter.select_drive(letter)

        matched = [d for d in self.presenter.current_drives if d.drive_letter == letter]
        if matched:
            d = matched[0]
            rec = DriveSpeedOptimizer.calculate_recommended_speed(d)
            # FIND-015 (REV-008): Format speed label based on BusType
            if d.bus_type == BusType.USB:
                bus_label = "External USB Safe"
            elif d.bus_type == BusType.SATA:
                bus_label = "SATA Internal"
            elif d.bus_type == BusType.ATAPI:
                bus_label = "ATAPI Internal"
            elif d.bus_type == BusType.VIRTUAL:
                bus_label = "Virtual CD Mode"
            else:
                bus_label = "Standard Safe"
            self.lbl_speed_info.config(text=f"Recommended: {rec}x ({bus_label})")

    def _on_toggle_virtual(self):
        self.presenter.switch_to_virtual_drive()

    def _display_toc(self, toc: DiscTOC):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for t in toc.tracks:
            mins = int(t.duration_seconds // 60)
            secs = int(t.duration_seconds % 60)
            time_str = f"{mins:02d}:{secs:02d}"
            self.tree.insert(
                "",
                tk.END,
                values=(t.track_number, f"Track {t.track_number:02d}", "Unknown Artist", time_str, "Ready"),
            )

    def _update_tracks_with_metadata(self, album: AlbumMetadata):
        # FIND-002: Safely handles toc is None
        matched_tracks, is_complete = ITunesApiClient.match_tracks_with_toc(
            self.presenter.current_toc, album, self.presenter.selected_disc
        )
        if self.presenter.current_toc and not is_complete:
            self._append_log("Warning: Track count or duration mismatch with CD TOC.")

        for item in self.tree.get_children():
            self.tree.delete(item)

        for toc_track, itunes_track in matched_tracks:
            if toc_track:
                mins = int(toc_track.duration_seconds // 60)
                secs = int(toc_track.duration_seconds % 60)
                time_str = f"{mins:02d}:{secs:02d}"
                trk_num = toc_track.track_number
            else:
                duration_sec = (itunes_track.duration_millis / 1000.0) if itunes_track else 0.0
                mins = int(duration_sec // 60)
                secs = int(duration_sec % 60)
                time_str = f"{mins:02d}:{secs:02d}"
                trk_num = itunes_track.track_number if itunes_track else 1

            title = itunes_track.track_title if itunes_track else f"Track {trk_num:02d}"
            artist = itunes_track.artist_name if itunes_track else album.artist_name
            self.tree.insert(
                "",
                tk.END,
                values=(trk_num, title, artist, time_str, "Ready"),
            )

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

        # FIND-006 (REV-004): Asynchronous non-blocking iTunes search
        def do_search():
            q_text = txt_q.get()
            btn_search.config(state=tk.DISABLED)
            lbl_status.config(text="Searching iTunes...")
            lst.delete(0, tk.END)
            albums_cache.clear()

            def worker():
                results = self.presenter.metadata_provider.search_albums(q_text)

                def update_ui():
                    btn_search.config(state=tk.NORMAL)
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
            self.presenter.apply_album_metadata(chosen.collection_id)
            dlg.destroy()

        btn_apply = ttk.Button(dlg, text="Apply Selected Album", command=on_select)
        btn_apply.pack(pady=10)

        do_search()

    def _on_start_rip(self):
        # FIND-001 (REV-001): Guard against starting without a loaded TOC
        if not self.presenter.current_toc:
            messagebox.showwarning("Notice", "No CD loaded or TOC available to rip.")
            self.btn_start_rip.config(state=tk.NORMAL)
            self.btn_cancel.config(state=tk.DISABLED)
            return

        out_dir = self.txt_outdir.get().strip()
        if not out_dir:
            messagebox.showerror("Error", "Please specify an output folder.")
            return

        fmt = EncodeFormat(self.format_var.get())
        speed_str = self.speed_var.get()
        if speed_str.startswith("Auto"):
            speed = (
                self.presenter.selected_drive.recommended_speed_x
                if self.presenter.selected_drive
                else 8
            )
        else:
            speed = int(speed_str.replace("x", "").replace("Max", "24"))

        config = RipConfig(
            output_dir=out_dir,
            format=fmt,
            selected_speed_x=speed,
        )

        self.btn_start_rip.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.NORMAL)
        self.presenter.start_ripping(config)

    def _append_log(self, text: str):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, f"{text}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)