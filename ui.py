import os
import threading
import ctypes
import time
import math
from pathlib import Path
from collections import deque
from datetime import datetime

import customtkinter as ctk
import psutil
from openpyxl import Workbook
from tkinter import ttk, messagebox, Canvas
from PIL import Image

from helpers import is_admin, format_size, browser_running_improved
from system_tools import CpuSpeedReader, check_basic_tools
from cleaners import clean_folder


PREVIEW_SAMPLE_ROWS = 30
CPU_READER_INIT_DELAY_MS = 500


class SplashScreen:
    def __init__(self, parent):
        self.parent = parent
        self.root = ctk.CTkToplevel(parent)
        self.root.overrideredirect(True)
        self.root.configure(fg_color="#101820")

        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        img_path = Path("MCleaner.png")

        if img_path.exists():
            img = Image.open(img_path).convert("RGBA")
            ratio = img.height / img.width
            w, h = 360, int(360 * ratio)

            self.image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            ctk.CTkLabel(self.root, image=self.image, text="").pack(fill="both", expand=True)

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - (h + 40)) // 2

            self.root.geometry(f"{w}x{h+40}+{x}+{y}")
        else:
            self.root.geometry("360x220")
            ctk.CTkLabel(self.root, text="MCleaner", font=("Segoe UI", 26, "bold")).pack(expand=True)

        ctk.CTkLabel(self.root, text="v0.7", font=("Segoe UI", 11, "bold")).place(relx=0.5, rely=0.85, anchor="center")
        ctk.CTkLabel(self.root, text="Initializing cleanup engine...", font=("Segoe UI", 10)).place(relx=0.5, rely=0.92, anchor="center")

        self.root.attributes("-alpha", 0.0)
        self.fade_in()

        # auto close splash after startup delay
        self.root.after(2200, self.close)

    def fade_in(self):
        try:
            a = self.root.attributes("-alpha")
            if a < 1:
                self.root.attributes("-alpha", min(1, a + 0.08))
                self.root.after(40, self.fade_in)
        except Exception:
            pass

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class MCleaner:
    def __init__(self, root):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = root
        self.root.title(f"MCleaner v0.7 {'(Administrator)' if is_admin() else '(Standard Mode)'}")
        self.root.geometry("1200x780")
        self.root.minsize(1080, 700)

        self.preview_ready = {"temp": False, "user_temp": False}
        self.badge_frames = []
        self.busy = False
        self.cpu_reader = None

        self.cpu_history = deque([0] * 80, maxlen=80)
        self.ram_history = deque([0] * 80, maxlen=80)
        self.disk_history = deque([0] * 80, maxlen=80)

        # cumulative stats
        self.reset_stats()
        self._build_ui()

        self.root.after(CPU_READER_INIT_DELAY_MS, self.init_cpu_reader)
        self.root.after(300, self.update_dashboard)
        self.animate_badges()

    def reset_stats(self):
        self.last_cleaned = 0
        self.last_size_mb = 0.0
        self.protected_count = 0

    def init_cpu_reader(self):
        self.cpu_reader = CpuSpeedReader()

    def set_table_headers(self, h1="File", h2="Size", h3="Status"):
        self.table.heading("file", text=h1)
        self.table.heading("size", text=h2)
        self.table.heading("status", text=h3)

    def _build_ui(self):
        main = ctk.CTkFrame(self.root)
        main.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(main, width=260, corner_radius=20)
        sidebar.pack(side="left", fill="y", padx=14, pady=14)
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="MCleaner", font=("Segoe UI", 30, "bold")).pack(pady=(22, 5))
        ctk.CTkLabel(sidebar, text="v0.7 • Author: MAF", font=("Segoe UI", 12)).pack(pady=(0, 12))

        buttons = [
            ("⚡ Clean Everything", self.clean_all, 56),
            ("🧹 Preview Windows Temp", self.handle_temp_button, 48),
            ("🧹 Preview User Temp", self.handle_user_temp_button, 48),
            ("🌐 Clean Browser Cache", self.clean_browser_cache, 48),
            ("🗑 Empty Recycle Bin", self.clean_recycle_bin, 48),
            ("📄 Export Report", self.export_excel_report, 48),
            ("🔧 Runtime checker", self.check_basic_tools, 48),
        ]

        refs = []
        for text, cmd, h in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                height=h,
                width=220,
                corner_radius=16 if h == 56 else 14,
                fg_color="#1f2937",
                hover_color="#2b6ef6",
                command=cmd
            )
            btn.pack(fill="x", padx=14, pady=6)
            refs.append(btn)

        # store references to the main buttons so we can safely enable/disable them
        self.clean_everything_btn, self.temp_button, self.user_temp_button = refs[:3]
        self.sidebar_buttons = refs

        content = ctk.CTkFrame(main)
        content.pack(side="right", fill="both", expand=True, padx=14, pady=14)

        perf = ctk.CTkFrame(content, fg_color="transparent")
        perf.pack(fill="x", pady=10)

        self.cpu_card = self.make_perf_card(perf, "CPU", "#3b82f6")
        self.ram_card = self.make_perf_card(perf, "Memory", "#8b5cf6")
        self.disk_card = self.make_perf_card(perf, "Disk", "#10b981")

        stats = ctk.CTkFrame(content, fg_color="transparent")
        stats.pack(fill="x", pady=8)

        self.card_recoverable = self.make_stat_badge(stats, "Recoverable", "   0.00 MB")
        self.card_deleted = self.make_stat_badge(stats, "Deleted", "0 files")
        self.card_protected = self.make_stat_badge(stats, "Permission Needed", "0 files")

        self.progress = ctk.CTkProgressBar(content)
        self.progress.pack(fill="x", padx=10, pady=10)
        self.progress.set(0)

        table_frame = ctk.CTkFrame(content)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#111827", foreground="white", fieldbackground="#111827", rowheight=30)
        style.configure("Treeview.Heading", background="#1f2937", foreground="white")
        style.map("Treeview", background=[("selected", "#2563eb")])

        self.table = ttk.Treeview(table_frame, columns=("file", "size", "status"), show="headings")

        for col, width in zip(("file", "size", "status"), (560, 130, 240)):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscroll=scrollbar.set)

        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def make_perf_card(self, parent, title, color):
        frame = ctk.CTkFrame(parent, height=110, corner_radius=16, width=1)
        frame.pack(side="left", fill="both", expand=True, padx=5)
        frame.pack_propagate(False)

        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        value = ctk.CTkLabel(frame, text="0", font=("Segoe UI", 13))
        value.pack(anchor="w", padx=10)

        graph = Canvas(frame, height=40, bg="#1a1a1a", highlightthickness=0)
        graph.pack(fill="x", padx=8, pady=5)

        return {
            "value": value,
            "graph": graph,
            "color": color,
            "line_id": graph.create_line(0, 20, 1, 20, fill=color, width=2, smooth=True)
        }

    def make_stat_badge(self, parent, title, value):
        frame = ctk.CTkFrame(parent, height=70, corner_radius=18, fg_color="#111827")
        frame.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
        val = ctk.CTkLabel(frame, text=value, font=("Segoe UI", 12))
        val.pack()

        self.badge_frames.append((frame, val))
        return val

    def draw_graph(self, canvas, data, color, line_id):
        canvas.update_idletasks()

        w = canvas.winfo_width()
        h = canvas.winfo_height()

        if w < 10:
            return

        step = w / max(len(data) - 1, 1)

        pts = []
        for i, v in enumerate(data):
            x = i * step
            y = h - (max(0, min(100, v)) / 100 * h)
            pts.extend((x, y))

        canvas.coords(line_id, *pts)

    def animate_badges(self, phase=0):
        for i, (frame, _) in enumerate(self.badge_frames):
            factor = 1 + 0.05 * math.sin(phase + i)
            c = int(17 * factor)
            frame.configure(fg_color=f"#{c:02x}{24:02x}{39:02x}")

        self.root.after(140, lambda: self.animate_badges(phase + 0.25))

    def update_dashboard(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        ghz = self.cpu_reader.read() if self.cpu_reader else 0
        cores = psutil.cpu_count(logical=True) or 0

        self.cpu_history.append(cpu)
        self.ram_history.append(ram.percent)
        self.disk_history.append(disk.percent)

        self.cpu_card["value"].configure(text=f"{cpu:.0f}% {ghz:.2f} GHz / {cores} threads")
        self.ram_card["value"].configure(text=f"{ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB ({ram.percent:.0f}%)")
        self.disk_card["value"].configure(text=f"{disk.percent:.0f}% used")

        for card, hist in (
            (self.cpu_card, self.cpu_history),
            (self.ram_card, self.ram_history),
            (self.disk_card, self.disk_history),
        ):
            self.draw_graph(card["graph"], hist, card["color"], card["line_id"])

        self.root.after(1000, self.update_dashboard)

    def add_rows_batch(self, rows):
        for r in rows:
            self.table.insert("", "end", values=r)

    def clear_table(self):
        for row in self.table.get_children():
            self.table.delete(row)

    def update_stats(self):
        self.card_deleted.configure(text=f"{self.last_cleaned} files")
        self.card_recoverable.configure(text=f"{self.last_size_mb:.2f} MB")
        self.card_protected.configure(text=f"{self.protected_count} files")
        self.progress.set(0)

    def preview_files(self, folder: Path):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        rows, total = [], 0
        for i, path in enumerate((Path(r) / f for r, _, fs in os.walk(folder) for f in fs)):
            if i >= PREVIEW_SAMPLE_ROWS:
                break
            try:
                size = path.stat().st_size
                total += size
                rows.append((path.name, format_size(size), "Ready to clean"))
            except Exception:
                pass

        self.add_rows_batch(rows)
        self.card_recoverable.configure(text=f"{total/(1024**2):.2f} MB (sample)")

    def toggle_preview_clean(self, key, folder, button, preview_text, clean_text):
        if not self.preview_ready[key]:
            self.preview_files(folder)
            button.configure(text=clean_text)
        else:
            # When toggling from preview -> clean, ask for confirmation and run the cleaner
            self.confirm_and_clean(folder)
            button.configure(text=preview_text)

        self.preview_ready[key] = not self.preview_ready[key]

    def handle_temp_button(self):
        self.toggle_preview_clean(
            "temp",
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            self.temp_button,
            "🧹 Preview Windows Temp",
            "🧹 Clean Windows Temp"
        )

    def handle_user_temp_button(self):
        self.toggle_preview_clean(
            "user_temp",
            Path(os.path.expandvars(r"%temp%")),
            self.user_temp_button,
            "🧹 Preview User Temp",
            "🧹 Clean User Temp"
        )

    def confirm_and_clean(self, folder):
        """
        Confirm and clean a single folder. Uses snapshots of the counters so we can report deltas
        back into the UI. This avoids depending on the return value/type of `clean_folder`.
        """
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        prompt = f"Remove files in:\n{folder}\n\nThis will attempt to delete temporary files. Continue?"
        if not messagebox.askyesno("Confirm Cleanup", prompt):
            return

        # Prepare UI
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            prev_files = self.last_cleaned
            prev_size = self.last_size_mb
            prev_prot = self.protected_count

            try:
                clean_folder(folder, self)
            except Exception as e:
                # schedule error row
                self.root.after(0, lambda: self.add_rows_batch([(str(folder), "-", f"Error: {e}")]))
            finally:
                # compute deltas
                d_files = max(0, self.last_cleaned - prev_files)
                d_mb = max(0.0, self.last_size_mb - prev_size)
                d_prot = max(0, self.protected_count - prev_prot)

                def finish_ui():
                    self.add_rows_batch([(str(folder), f"{d_files} files", f"Recovered {d_mb:.2f} MB • {d_prot} protected")])
                    self.update_stats()
                    # done
                    self.set_busy(False)

                self.root.after(0, finish_ui)

        threading.Thread(target=worker, daemon=True).start()

    def clean_browser_cache(self):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        if browser_running_improved():
            messagebox.showwarning("Browser Open", "Please close Chrome or Edge before cleaning browser cache.")
            return

        # If you have a dedicated browser cleaner that reports back, call it here.
        # For now, we just notify user (this keeps behavior consistent).
        self.add_rows_batch([("Browser Cache", "-", "Cleaning not implemented in this build")])

    def clean_recycle_bin(self):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        try:
            # Attempt to empty recycle bin. Flags: 0x1 = SHERB_NOCONFIRMATION (we pass 1 here to try to suppress dialogs),
            # but keep this simple and rely on Windows API.
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            self.add_rows_batch([("Recycle Bin", "-", "Emptied successfully")])
        except Exception as e:
            self.add_rows_batch([("Recycle Bin", "-", f"Error: {e}")])
        finally:
            # ensure busy state is cleared if this was used as the final step of clean_all
            self.set_busy(False)

    def clean_all(self):
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%"))
        ]

        # Ask for confirmation with explicit list of folders and recycle bin
        msg = "The following locations will be cleaned:\n\n"
        msg += "\n".join(str(p) for p in folders)
        msg += "\n\nRecycle Bin will also be emptied. This may delete files permanently. Continue?"

        if not messagebox.askyesno("Confirm Full Cleanup", msg):
            return

        # UI prep
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            total_before_files = self.last_cleaned
            total_before_size = self.last_size_mb
            total_before_prot = self.protected_count

            for folder in folders:
                # mark starting row immediately on main thread
                self.root.after(0, lambda f=folder: self.add_rows_batch([(str(f), "-", "Cleaning...")]))

                prev_files = self.last_cleaned
                prev_size = self.last_size_mb
                prev_prot = self.protected_count

                try:
                    # call the cleaner for this folder. We pass unlock=False to avoid dangerous unlock attempts across all items.
                    clean_folder(folder, self, unlock=False)
                except Exception as e:
                    # schedule an error line
                    self.root.after(0, lambda f=folder, ee=e: self.add_rows_batch([(str(f), "-", f"Error: {ee}")]))
                    continue

                # compute deltas after the call
                d_files = max(0, self.last_cleaned - prev_files)
                d_mb = max(0.0, self.last_size_mb - prev_size)
                d_prot = max(0, self.protected_count - prev_prot)

                # schedule UI update for this folder
                self.root.after(0, lambda f=folder, df=d_files, dm=d_mb, dp=d_prot: self.add_rows_batch([
                    (str(f), f"{df} files", f"Recovered {dm:.2f} MB • {dp} protected")
                ]))

            # After cleaning folders, empty recycle bin on main thread (it will also clear busy state there)
            self.root.after(0, self.clean_recycle_bin)

            # Finally schedule a consolidated summary row
            def final_summary():
                total_files = self.last_cleaned - total_before_files
                total_mb = self.last_size_mb - total_before_size
                total_prot = self.protected_count - total_before_prot
                self.add_rows_batch([("Summary", f"{total_files} files", f"Recovered {total_mb:.2f} MB • {total_prot} protected")])
                self.update_stats()

            self.root.after(0, final_summary)

        threading.Thread(target=worker, daemon=True).start()

    def check_basic_tools(self):
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        self.clear_table()
        self.set_table_headers("Tool", "Status", "Notes")

        results = check_basic_tools()
        self.add_rows_batch(results)

    def export_excel_report(self):
        fn = f"MCleaner_Report_{datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.append(["Deleted Files", self.last_cleaned])
        ws.append(["Recovered MB", f"{self.last_size_mb:.2f}"])
        ws.append(["Permission Needed", self.protected_count])
        wb.save(fn)

        self.add_rows_batch([(fn, "-", "Saved successfully")])

    def set_busy(self, value):
        """
        Set busy state and disable/enable all sidebar buttons to avoid conflicting operations.
        """
        self.busy = value
        state = "disabled" if value else "normal"

        for w in getattr(self, "sidebar_buttons", []):
            try:
                w.configure(state=state)
            except Exception:
                pass

    # end of class


if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()

    app = MCleaner(root)

    splash = None
    try:
        splash = SplashScreen(root)
    except Exception:
        pass

    def show_main():
        root.deiconify()
        if splash:
            try:
                splash.close()
            except Exception:
                pass

    root.after(2200, show_main)
    root.mainloop()
