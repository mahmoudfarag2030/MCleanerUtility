import os
import sys
import threading
import ctypes
import math
from pathlib import Path
from collections import deque
from datetime import datetime

from cleaners import clean_folder, clean_browser_cache as run_browser_clean

import customtkinter as ctk
import psutil
from openpyxl import Workbook
from tkinter import ttk, messagebox, Canvas
from PIL import Image

from installed_apps import get_installed_apps
from helpers import is_admin, format_size, browser_running_improved
from system_tools import CpuSpeedReader, check_basic_tools
from startup_apps import get_startup_apps, toggle_startup_app
from speed_test import run_speed_test

try:
    from scheduler_manager import create_task, delete_task, task_exists
except Exception:

    def create_task(*args, **kwargs):
        return False, "Scheduler module unavailable"

    def delete_task(*args, **kwargs):
        return False, "Scheduler module unavailable"

    def task_exists():
        return False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


PREVIEW_SAMPLE_ROWS = 30
APP_VERSION = "0.9.0"


def get_build_version():
    """Return a short build identifier based on the current git commit (if available)."""
    try:
        import subprocess
        from pathlib import Path

        repo_dir = Path(__file__).resolve().parent
        out = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


BUILD_VERSION = get_build_version()

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

        img_full_path = resource_path("MCleaner.png")
        img_path = Path(img_full_path)

        if img_path.exists():
            img = Image.open(img_path).convert("RGBA")
            ratio = img.height / img.width
            w, h = 360, int(360 * ratio)

            self.image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            img_label = ctk.CTkLabel(self.root, image=self.image, text="")
            img_label.pack(fill="both", expand=True)

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - (h + 60)) // 2  # add extra space for status labels

            self.root.geometry(f"{w}x{h+60}+{x}+{y}")

            footer = ctk.CTkFrame(self.root, fg_color="transparent")
            footer.pack(fill="x", side="bottom", pady=(6, 10))

            ctk.CTkLabel(
                footer,
                text=f"v{APP_VERSION} (build {BUILD_VERSION})",
                font=("Segoe UI", 11, "bold"),
            ).pack()
            ctk.CTkLabel(
                footer, text="Initializing cleanup engine...", font=("Segoe UI", 10)
            ).pack()
        else:
            self.root.geometry("360x220")
            ctk.CTkLabel(
                self.root, text="MCleaner", font=("Segoe UI", 26, "bold")
            ).pack(expand=True)

            ctk.CTkLabel(
                self.root, text=f"v{APP_VERSION}", font=("Segoe UI", 11, "bold")
            ).pack(pady=(8, 2))
            ctk.CTkLabel(
                self.root, text="Initializing cleanup engine...", font=("Segoe UI", 10)
            ).pack()

        self.root.attributes("-alpha", 0.0)
        self.fade_in()
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
        self.root.title(
            f"MCleaner v{APP_VERSION} (build {BUILD_VERSION}) {'(Administrator)' if is_admin() else '(Standard Mode)'}"
        )
        
        # Calculate responsive window size based on screen resolution
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Track UI scaling factor (affects widget/font scaling on high-DPI displays)
        scale = ctk.get_widget_scaling() or 1.0

        # Account for taskbar (approximately 50 pixels)
        available_height = screen_height - 50

        # For small screens (1366x768 and below), use more conservative sizing
        if screen_width <= 1366 and available_height <= 768:
            # Use 85% of screen size for small displays
            target_width = int(screen_width * 0.85)
            target_height = int(available_height * 0.85)
            # Minimum size for small screens
            min_width, min_height = 900, 600
        else:
            # Use 90% of available screen size for larger displays, but cap at reasonable maximums
            target_width = min(int(screen_width * 0.9), 1200)
            target_height = min(int(available_height * 0.9), 780)
            # Minimum size for larger screens
            min_width, min_height = 1080, 700

        # Ensure minimum usable size
        target_width = max(target_width, min_width)
        target_height = max(target_height, min_height)

        # If available screen is smaller than our minimum, use 95% of available size
        if screen_width < 1080 or available_height < 700:
            target_width = int(screen_width * 0.95)
            target_height = int(available_height * 0.95)

        # Apply scaling (shrink UI size on high-DPI / high-scaling displays)
        target_width = max(int(target_width / scale), 640)
        target_height = max(int(target_height / scale), 480)
        min_width = max(int(min_width / scale), 640)
        min_height = max(int(min_height / scale), 480)

        self.root.geometry(f"{target_width}x{target_height}")
        self.root.minsize(min_width, min_height)
        self.center_window(target_width, target_height)

        # Store for responsive layouts
        self.ui_scale = scale
        self.window_width = target_width
        self.window_height = target_height

        self.preview_ready = {"temp": False, "user_temp": False}
        self.badge_frames = []
        self.busy = False
        self.cpu_reader = None

        self.cpu_history = deque([0] * 80, maxlen=80)
        self.ram_history = deque([0] * 80, maxlen=80)
        self.disk_history = deque([0] * 80, maxlen=80)

        self.reset_stats()
        self._build_ui()

        self.root.after(CPU_READER_INIT_DELAY_MS, self.init_cpu_reader)
        self.root.after(300, self.update_dashboard)
        self.animate_badges()

    def reset_stats(self):
        self.last_cleaned = 0
        self.last_size_mb = 0.0
        self.protected_count = 0

    def center_window(self, width, height, parent=None):
        """Center a window on the screen or relative to a parent window."""
        win = parent if parent is not None else self.root
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        
        # Account for taskbar (typically 40-50 pixels at bottom)
        # Use available height minus a margin for taskbar
        available_h = screen_h - 50
        
        x = (screen_w - width) // 2
        y = (available_h - height) // 2
        
        # Ensure y is not negative (for very small screens)
        y = max(0, y)
        
        win.geometry(f"{width}x{height}+{x}+{y}")

    def init_cpu_reader(self):
        try:
            self.cpu_reader = CpuSpeedReader()
        except Exception:
            self.cpu_reader = None

    def set_table_headers(self, h1="File", h2="Size", h3="Status"):
        try:
            self.table.heading("file", text=h1)
            self.table.heading("size", text=h2)
            self.table.heading("status", text=h3)
        except Exception:
            pass

    def _build_ui(self):
        main = ctk.CTkFrame(self.root)
        main.pack(fill="both", expand=True)

        # Calculate responsive sidebar width based on screen size
        if screen_width <= 1366:
            # Smaller sidebar for small screens (18-20% of window width)
            sidebar_width = max(180, min(240, int(self.root.winfo_width() * 0.20)))
        else:
            # Standard sidebar for larger screens (20-22% of window width)
            sidebar_width = max(200, min(280, int(self.root.winfo_width() * 0.22)))
        
        # Determine padding based on screen size
        if screen_width <= 1366:
            sidebar_padding = (6, 6)
            content_padding = (6, 6)
            button_padding = (6, 3)
        else:
            sidebar_padding = (10, 10)
            content_padding = (10, 10)
            button_padding = (10, 4)

        sidebar = ctk.CTkFrame(main, width=sidebar_width, corner_radius=20)
        sidebar.pack(side="left", fill="y", padx=sidebar_padding[0], pady=sidebar_padding[1])
        sidebar.pack_propagate(False)

        # Determine font sizes based on screen size
        if screen_width <= 1366:
            title_font_size = 24
            version_font_size = 10
            button_height_main = 26
            button_height_secondary = 22
        else:
            title_font_size = 30
            version_font_size = 12
            button_height_main = 29
            button_height_secondary = 26

        ctk.CTkLabel(sidebar, text="MCleaner", font=("Segoe UI", title_font_size, "bold")).pack(
            pady=(16, 4)
        )
        ctk.CTkLabel(
            sidebar,
            text=f"v{APP_VERSION} (build {BUILD_VERSION}) • Author: MAF",
            font=("Segoe UI", version_font_size),
        ).pack(pady=(0, 8))

        buttons = [
            ("⚡ Clean Everything", self.clean_all, button_height_main),
            ("🧹 Preview Windows Temp", self.handle_temp_button, button_height_secondary),
            ("🧹 Preview User Temp", self.handle_user_temp_button, button_height_secondary),
            ("🌐 Clean Browser Cache", self.clean_browser_cache, button_height_secondary),
            ("🗑 Empty Recycle Bin", self.clean_recycle_bin, button_height_secondary),
            ("⏰ Scheduled Cleanup", self.open_scheduler_window, button_height_secondary),
            ("📦 Installed Apps", self.show_installed_apps, button_height_secondary),
            ("🚀 Startup Apps", self.show_startup_apps, button_height_secondary),
            ("📡 Internet Speed Test", self.run_speed_test_ui, button_height_secondary),
            ("🔧 Runtime checker", self.check_basic_tools, button_height_secondary),
        ]

        refs = []
        for text, cmd, h in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                height=h,
                corner_radius=16 if h == button_height_main else 14,
                fg_color="#1f2937",
                hover_color="#2b6ef6",
                command=cmd,
            )
            btn.pack(fill="x", padx=button_padding[0], pady=button_padding[1])
            refs.append(btn)

        self.clean_everything_btn, self.temp_button, self.user_temp_button = refs[:3]
        self.sidebar_buttons = refs

        content = ctk.CTkFrame(main)
        content.pack(side="right", fill="both", expand=True, padx=content_padding[0], pady=content_padding[1])

        # Determine UI element sizes based on screen size
        if screen_width <= 1366:
            perf_card_height = 47
            stat_badge_height = 32
            perf_title_font = ("Segoe UI", 10, "bold")
            perf_value_font = ("Segoe UI", 12)
            stat_title_font = ("Segoe UI", 9, "bold")
            stat_value_font = ("Segoe UI", 11)
            table_row_height = 14
        else:
            perf_card_height = 58
            stat_badge_height = 37
            perf_title_font = ("Segoe UI", 11, "bold")
            perf_value_font = ("Segoe UI", 13)
            stat_title_font = ("Segoe UI", 10, "bold")
            stat_value_font = ("Segoe UI", 12)
            table_row_height = 16

        perf = ctk.CTkFrame(content, fg_color="transparent")
        perf.pack(fill="x", pady=content_padding[0])

        self.cpu_card = self.make_perf_card(perf, "CPU", "#3b82f6", perf_card_height, perf_title_font, perf_value_font)
        self.ram_card = self.make_perf_card(perf, "Memory", "#8b5cf6", perf_card_height, perf_title_font, perf_value_font)
        self.disk_card = self.make_perf_card(perf, "Disk", "#10b981", perf_card_height, perf_title_font, perf_value_font)

        stats = ctk.CTkFrame(content, fg_color="transparent")
        stats.pack(fill="x", pady=content_padding[0]//2)

        self.card_recoverable = self.make_stat_badge(stats, "Recoverable", "   0.00 MB", stat_badge_height, stat_title_font, stat_value_font)
        self.card_deleted = self.make_stat_badge(stats, "Deleted", "0 files", stat_badge_height, stat_title_font, stat_value_font)
        self.card_protected = self.make_stat_badge(
            stats, "Permission Needed", "0 files", stat_badge_height, stat_title_font, stat_value_font
        )

        self.progress = ctk.CTkProgressBar(content)
        self.progress.pack(fill="x", padx=content_padding[0], pady=content_padding[0])
        self.progress.set(0)

        table_frame = ctk.CTkFrame(content)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Treeview",
            background="#111827",
            foreground="white",
            fieldbackground="#111827",
            rowheight=table_row_height,
        )
        style.configure("Treeview.Heading", background="#1f2937", foreground="white")
        style.map("Treeview", background=[("selected", "#2563eb")])

        self.table = ttk.Treeview(
            table_frame, columns=("file", "size", "status"), show="headings"
        )

        # Make table columns responsive to window size
        def update_table_columns(event=None):
            try:
                table_width = self.table.winfo_width()
                if table_width > 100:  # Only update if table has been sized
                    # Allocate space proportionally: file (60%), size (15%), status (25%)
                    if screen_width <= 1366:
                        # Smaller minimum widths for small screens
                        file_width = max(int(table_width * 0.6), 150)
                        size_width = max(int(table_width * 0.15), 60)
                        status_width = max(table_width - file_width - size_width, 100)
                    else:
                        # Standard minimum widths for larger screens
                        file_width = max(int(table_width * 0.6), 200)
                        size_width = max(int(table_width * 0.15), 80)
                        status_width = max(table_width - file_width - size_width, 120)
                    
                    self.table.column("file", width=file_width)
                    self.table.column("size", width=size_width)
                    self.table.column("status", width=status_width)
            except Exception:
                pass

        self.table.bind("<Configure>", update_table_columns)

        for col in ("file", "size", "status"):
            self.table.heading(col, text=col.title())
            if screen_width <= 1366:
                # Smaller initial widths for small screens
                initial_widths = {"file": 150, "size": 60, "status": 100}
            else:
                # Standard initial widths for larger screens
                initial_widths = {"file": 200, "size": 80, "status": 120}
            self.table.column(col, width=initial_widths[col])  # Initial width, will be updated

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.table.yview
        )
        self.table.configure(yscroll=scrollbar.set)

        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def make_perf_card(self, parent, title, color, height=110, title_font=("Segoe UI", 11, "bold"), value_font=("Segoe UI", 13)):
        frame = ctk.CTkFrame(parent, height=height, corner_radius=16, width=1)
        frame.pack(side="left", fill="both", expand=True, padx=4)
        frame.pack_propagate(False)

        ctk.CTkLabel(frame, text=title, font=title_font).pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        value = ctk.CTkLabel(frame, text="0", font=value_font)
        value.pack(anchor="w", padx=8)

        graph = Canvas(frame, height=21, bg="#1a1a1a", highlightthickness=0)
        graph.pack(fill="x", padx=6, pady=4)

        line_id = graph.create_line(0, 20, 1, 20, fill=color, width=2, smooth=True)

        return {
            "value": value,
            "graph": graph,
            "color": color,
            "line_id": line_id,
        }

    def make_stat_badge(self, parent, title, value, height=70, title_font=("Segoe UI", 10, "bold"), value_font=("Segoe UI", 12)):
        frame = ctk.CTkFrame(parent, height=height, corner_radius=18, fg_color="#111827")
        frame.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(frame, text=title, font=title_font).pack(pady=(6, 2))
        val = ctk.CTkLabel(frame, text=value, font=value_font)
        val.pack()

        self.badge_frames.append((frame, val))
        return val

    def draw_graph(self, canvas, data, color, line_id):
        try:
            canvas.update_idletasks()
            w = canvas.winfo_width()
            h = canvas.winfo_height()

            if w < 10 or h < 5:
                return

            step = w / max(len(data) - 1, 1)

            pts = []
            for i, v in enumerate(data):
                x = i * step
                y = h - (max(0, min(100, v)) / 100 * h)
                pts.extend((x, y))

            canvas.coords(line_id, *pts)
        except Exception:
            pass

    def animate_badges(self, phase=0):
        for i, (frame, _) in enumerate(self.badge_frames):
            factor = 1 + 0.05 * math.sin(phase + i)
            c = int(17 * factor)
            try:
                frame.configure(fg_color=f"#{c:02x}{24:02x}{39:02x}")
            except Exception:
                pass

        self.root.after(140, lambda: self.animate_badges(phase + 0.25))

    def update_dashboard(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            ghz = (
                self.cpu_reader.read()
                if self.cpu_reader and hasattr(self.cpu_reader, "read")
                else 0
            )
            cores = psutil.cpu_count(logical=True) or 0

            self.cpu_history.append(cpu)
            self.ram_history.append(ram.percent)
            self.disk_history.append(disk.percent)

            self.cpu_card["value"].configure(
                text=f"{cpu:.0f}% {ghz:.2f} GHz / {cores} threads"
            )
            self.ram_card["value"].configure(
                text=f"{ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB ({ram.percent:.0f}%)"
            )
            self.disk_card["value"].configure(text=f"{disk.percent:.0f}% used")

            for card, hist in (
                (self.cpu_card, self.cpu_history),
                (self.ram_card, self.ram_history),
                (self.disk_card, self.disk_history),
            ):
                self.draw_graph(card["graph"], hist, card["color"], card["line_id"])
        except Exception:
            pass

        self.root.after(1000, self.update_dashboard)

    def add_rows_batch(self, rows):
        for r in rows:
            try:
                self.table.insert("", "end", values=r[:3])
            except Exception:
                pass

    def clear_table(self):
        for row in list(self.table.get_children()):
            try:
                self.table.delete(row)
            except Exception:
                pass

    def update_stats(self):
        try:
            self.card_deleted.configure(text=f"{self.last_cleaned} files")
            self.card_recoverable.configure(text=f"{self.last_size_mb:.2f} MB")
            self.card_protected.configure(text=f"{self.protected_count} files")
            self.progress.set(0)
        except Exception:
            pass

    def set_progress(self, value: float):
        """Update the progress bar (expects a value between 0 and 1)."""
        try:
            v = max(0.0, min(1.0, float(value)))
            self.progress.set(v)
        except Exception:
            pass

    def preview_files(self, folder: Path):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        rows, total = [], 0
        try:
            i = 0
            for root_dir, _, files in os.walk(folder):
                for fname in files:
                    if i >= PREVIEW_SAMPLE_ROWS:
                        break
                    try:
                        path = Path(root_dir) / fname
                        size = path.stat().st_size
                        total += size
                        rows.append((path.name, format_size(size), "Ready to clean"))
                        i += 1
                    except Exception:
                        continue
                if i >= PREVIEW_SAMPLE_ROWS:
                    break
        except Exception:
            pass

        self.add_rows_batch(rows)
        self.card_recoverable.configure(text=f"{total/(1024**2):.2f} MB (sample)")

    def toggle_preview_clean(self, key, folder, button, preview_text, clean_text):
        if not self.preview_ready.get(key, False):
            self.preview_files(folder)
            button.configure(text=clean_text)
        else:
            self.confirm_and_clean(folder)
            button.configure(text=preview_text)

        self.preview_ready[key] = not self.preview_ready.get(key, False)

    def handle_temp_button(self):
        self.toggle_preview_clean(
            "temp",
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            self.temp_button,
            "🧹 Preview Windows Temp",
            "🧹 Clean Windows Temp",
        )

    def handle_user_temp_button(self):
        self.toggle_preview_clean(
            "user_temp",
            Path(os.path.expandvars(r"%temp%")),
            self.user_temp_button,
            "🧹 Preview User Temp",
            "🧹 Clean User Temp",
        )

    def confirm_and_clean(self, folder):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
            return

        if not messagebox.askyesno(
            "Confirm Cleanup", f"Remove files in:\n{folder}\n\nContinue?"
        ):
            return

        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            try:
                clean_folder(folder, self)
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def clean_browser_cache(self):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        if browser_running_improved():
            messagebox.showwarning(
                "Browser Open",
                "Please close Chrome or Edge before cleaning browser cache.",
            )
            return

        self.reset_stats()
        self.set_busy(True)

        def worker():
            try:
                run_browser_clean(self)
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def clean_recycle_bin(self):
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.set_busy(True)

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            self.add_rows_batch([("Recycle Bin", "-", "Emptied successfully")])
        except Exception as e:
            self.add_rows_batch([("Recycle Bin", "-", f"Error: {e}")])
        finally:
            self.update_stats()
            self.set_busy(False)

    def clean_all(self):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
            return

        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%")),
        ]

        if not messagebox.askyesno(
            "Confirm Full Cleanup", "Clean all temporary folders and recycle bin?"
        ):
            return

        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            for folder in folders:
                try:
                    clean_folder(folder, self, unlock=False)
                except Exception as e:
                    self.root.after(
                        0,
                        lambda ee=e: self.add_rows_batch(
                            [(str(folder), "-", f"Error: {ee}")]
                        ),
                    )

            try:
                ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            except Exception:
                pass

            self.root.after(0, self.update_stats)
            self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def show_installed_apps(self):
        self.clear_table()
        self.set_table_headers("Application", "Version", "Publisher")

        try:
            apps = get_installed_apps()
            self.add_rows_batch(apps if apps else [("No applications found", "-", "-")])
        except Exception as e:
            self.add_rows_batch([("Installed Apps", "-", f"Error: {e}")])

    def show_startup_apps(self):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
            return

        try:
            self.table.unbind("<Double-1>")
        except Exception:
            pass

        self.clear_table()
        self.set_table_headers("Application", "Status", "Source")

        try:
            apps = get_startup_apps()

            if not apps:
                self.add_rows_batch([("No startup apps found", "-", "-")])
                return

            visible_rows = [(a[0], a[1], a[2]) for a in apps]
            self.add_rows_batch(visible_rows)

            startup_map = {a[0]: a for a in apps}

            def toggle_selected(event):
                try:
                    row_id = self.table.identify_row(event.y)
                    if not row_id:
                        return

                    values = self.table.item(row_id).get("values", [])
                    if not values:
                        return

                    app_name = values[0]
                    item = startup_map.get(app_name)
                    if not item:
                        return

                    enable = item[1].lower() == "disabled"

                    result = toggle_startup_app(app_name, enable, registry_name=item[3])

                    ok = result[0] if isinstance(result, tuple) else bool(result)
                    msg = (
                        result[1]
                        if isinstance(result, tuple) and len(result) > 1
                        else None
                    )

                    if ok:
                        self.show_startup_apps()
                    else:
                        messagebox.showwarning("Startup Apps", msg or "Toggle failed")

                except Exception as e:
                    messagebox.showerror("Startup Apps", f"Toggle failed: {e}")

            self.table.bind("<Double-1>", toggle_selected)

        except Exception as e:
            self.add_rows_batch([("Startup Apps", "-", f"Error: {e}")])

    def run_speed_test_ui(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Speed Test")
        win.geometry("210x116")
        self.center_window(210, 116, parent=win)
        win.transient(self.root)
        win.lift()
        win.focus_force()
        try:
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
        except Exception:
            pass

        # Ensure the main UI is blocked while the speed test runs
        self.set_busy(True)
        try:
            win.grab_set()
        except Exception:
            pass

        def on_close():
            try:
                win.grab_release()
            except Exception:
                pass
            self.set_busy(False)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        lbl = ctk.CTkLabel(body, text="Running speed test...")
        lbl.pack(pady=(4, 6))

        prog = ctk.CTkProgressBar(body, mode="indeterminate")
        prog.pack(fill="x", pady=(2, 6))
        prog.start()

        def worker():
            res = run_speed_test()

            def finish():
                prog.stop()
                txt = f"Ping: {res['ping']} ms\nDownload: {res['download']} Mbps\nUpload: {res['upload']} Mbps"
                messagebox.showinfo("Speed Test Results", txt)
                on_close()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_basic_tools(self):
        self.clear_table()
        self.set_table_headers("Tool", "Status", "Notes")

        try:
            self.add_rows_batch(check_basic_tools())
        except Exception as e:
            self.add_rows_batch([("Runtime Check", "-", f"Error: {e}")])

    def export_excel_report(self):
        fn = f"MCleaner_Report_{datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Deleted Files", self.last_cleaned])
        ws.append(["Recovered MB", f"{self.last_size_mb:.2f}"])
        ws.append(["Permission Needed", self.protected_count])

        try:
            wb.save(fn)
            self.add_rows_batch([(fn, "-", "Saved successfully")])
        except Exception as e:
            self.add_rows_batch([(fn, "-", f"Error: {e}")])

    def open_scheduler_window(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Scheduled Cleanup")
        win.geometry("210x294")
        win.resizable(False, False)
        self.center_window(210, 294, parent=win)
        win.transient(self.root)
        win.lift()
        win.focus_force()
        try:
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
        except Exception:
            pass

        # Prevent interactions with the main window while scheduler is open
        self.set_busy(True)
        try:
            win.grab_set()
        except Exception:
            pass

        def on_close():
            try:
                win.grab_release()
            except Exception:
                pass
            self.set_busy(False)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=(10, 16))

        ctk.CTkLabel(
            body, text="Automatic Cleanup Scheduler", font=("Segoe UI", 18, "bold")
        ).pack(pady=(5, 11))

        mode = ctk.StringVar(value="Weekly")

        for option in ["Daily", "Weekly", "Monthly"]:
            ctk.CTkRadioButton(body, text=option, variable=mode, value=option).pack(
                pady=4
            )

        status_label = ctk.CTkLabel(
            body, text=f"Current: {'Active' if task_exists() else 'Not active'}"
        )
        status_label.pack(pady=(10, 10))

        def create_schedule():
            ok, msg = create_task(sys.executable, mode.get())
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(
                text=f"Current: {'Active' if task_exists() else 'Not active'}"
            )

        def remove_schedule():
            ok, msg = delete_task()
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(
                text=f"Current: {'Active' if task_exists() else 'Not active'}"
            )

        ctk.CTkButton(
            body, text="Create Schedule", width=190, height=23, command=create_schedule
        ).pack(pady=(10, 6))
        ctk.CTkButton(
            body,
            text="Remove Schedule",
            width=190,
            height=23,
            fg_color="#991b1b",
            hover_color="#b91c1c",
            command=remove_schedule,
        ).pack()

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for w in getattr(self, "sidebar_buttons", []):
            try:
                w.configure(state=state)
            except Exception:
                pass


if __name__ == "__main__":
    if "--run-silent" in sys.argv or "--run_silent" in sys.argv:
        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%")),
        ]

        for folder in folders:
            try:
                clean_folder(folder, None)
            except Exception as e:
                print("Scheduled cleanup error for", folder, e)

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
        except Exception:
            pass

        print("Scheduled cleanup finished")
        sys.exit(0)

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
